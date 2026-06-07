# client.py
#
# PURPOSE: Talk to arXiv's API, download paper metadata,
# parse the XML responses and download PDFs.
#
# MAIN CLASS: ArxivClient
#
# HOW IT'S USED:
#   client = ArxivClient(settings)
#   papers = await client.fetch_papers(max_results=100)
#
# NOTE: All fetch methods are async — they must be called
# with 'await' inside an async function.

import httpx
import logging
import time
import asyncio
from pathlib import Path
from urllib.parse import urlencode, quote
from functools import cached_property
from typing import List, Optional
from src.config import ArxivSettings
from src.exceptions import ArxivAPIException, ArxivAPITimeoutError, PDFDownloadException, PDFDownloadTimeoutError
from src.schemas.arxiv.paper import ArxivPaper
from src.services.arxiv.xml_parser import ArxivXmlParser

logger = logging.getLogger(__name__)


class ArxivClient:
    """
    Client for fetching papers from the arXiv API.

    Handles:
    - Rate limiting (arXiv recommends 3 seconds between requests)
    - PDF downloading with retry logic

    Usage:
        client = ArxivClient(settings=settings.arxiv)
        papers = await client.fetch_papers(max_results=50)
    """

    def __init__(self, settings: ArxivSettings):
        self._settings = settings
        self._last_request_time: Optional[float] = None
        self._parser = ArxivXmlParser(namespaces=settings.namespaces)
        # Adding a lock so concurrent requests don't both fire
        # at the same time, bypassing the rate limiter.
        #
        # Without this lock:
        #   Request A reads _last_request_time → sleeps 2s
        #   Request B reads _last_request_time → sleeps 2s (same value!)
        #   Both wake up and fire at the same time → rate limit broken
        #
        # With this lock:
        #   Request A acquires lock → checks time → sleeps → fires → releases
        #   Request B waits → acquires lock → checks time → fires → releases
        #   Requests are always separated by the required delay
        self._rate_limit_lock = asyncio.Lock()

    # --- Properties ---
    # These are just clean shortcuts to settings values.
    # Using @property means you write client.base_url instead
    # of client._settings.base_url everywhere.

    @cached_property
    def pdf_cache_dir(self) -> Path:
        """
        Local folder where downloaded PDFs are stored.
        Created automatically if it doesn't exist.
        
        Uses @cached_property so the folder is only created
        once, not on every access.
        """
        cache_dir = Path(self._settings.pdf_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @property
    def base_url(self) -> str:
        """Base URL for the arXiv API."""
        return self._settings.base_url

    @property
    def namespaces(self) -> dict:
        """XML namespaces used when parsing arXiv responses."""
        return self._settings.namespaces

    @property
    def rate_limit_delay(self) -> float:
        """Seconds to wait between API requests (arXiv recommends 3s)."""
        return self._settings.rate_limit_delay

    @property
    def timeout_seconds(self) -> int:
        """How long to wait for a response before giving up."""
        return self._settings.timeout_seconds

    @property
    def max_results(self) -> int:
        """Default number of papers to fetch if not specified."""
        return self._settings.max_results

    @property
    def search_category(self) -> str:
        """arXiv category to search (e.g. 'cs.AI')."""
        return self._settings.search_category

    # --- Rate limiting ---

    async def _apply_rate_limit(self) -> None:
        """
        Wait if needed so we don't send requests too fast.

        arXiv asks for 3 seconds between requests. This method
        checks how long it's been since the last request and
        sleeps only for the remaining time needed.

        The lock ensures only one request runs this check at a
        time, preventing two simultaneous requests from both
        seeing the same _last_request_time and both firing.

        Example:
            Last request was 1 second ago.
            Rate limit delay is 3 seconds.
            We sleep for 2 more seconds, then proceed.
        """
        async with self._rate_limit_lock:
            if self._last_request_time is not None:
                elapsed = time.time() - self._last_request_time
                remaining = self.rate_limit_delay - elapsed

                if remaining > 0:
                    logger.debug(f"Rate limiting: waiting {remaining:.1f}s")
                    await asyncio.sleep(remaining)

            self._last_request_time = time.time()
        
    # --- Internal helper ---

    def _build_url(self, params: dict, safe: str = ":+[]") -> str:
        """
        Build a full arXiv API URL from query parameters.

        Keeping URL building in one place means if arXiv ever
        changes their URL format, we fix it in one spot only.

        Args:
            params: Query parameters (search_query, max_results etc.)
            safe:   Characters that should NOT be URL-encoded.
                    arXiv needs :, +, [ ] kept as-is in queries.

        Returns:
            Full URL string ready to be requested

        Example:
            params = {"search_query": "cat:cs.AI", "max_results": 10}
            → "https://export.arxiv.org/api/query?search_query=cat:cs.AI&max_results=10"
        """
        return f"{self.base_url}?{urlencode(params, quote_via=quote, safe=safe)}"

    async def _get(self, url: str) -> str:
        """
        Make a single GET request to arXiv, respecting rate limits.

        This is the ONE place where HTTP requests happen.
        All fetch methods call this instead of making their
        own httpx calls — so rate limiting, timeout, and
        error handling are consistent everywhere.

        Args:
            url: Full URL to request

        Returns:
            Response body as text (XML from arXiv)

        Raises:
            ArxivAPITimeoutError: if the request takes too long
            ArxivAPIException:    if arXiv returns an error or
                                  something unexpected happens
        """
        await self._apply_rate_limit()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text

        except httpx.TimeoutException as e:
            # Timeout = arXiv took too long to respond
            logger.error(f"arXiv API timeout: {e}")
            raise ArxivAPITimeoutError(f"arXiv API request timed out: {e}") from e

        except httpx.HTTPStatusError as e:
            # HTTP error = arXiv responded but with an error code
            # e.g. 429 Too Many Requests, 503 Service Unavailable
            logger.error(f"arXiv API HTTP error {e.response.status_code}: {e}")
            raise ArxivAPIException(
                f"arXiv API returned error {e.response.status_code}: {e}"
            ) from e

        except Exception as e:
            # Catch-all for anything unexpected
            logger.error(f"Unexpected error calling arXiv API: {e}")
            raise ArxivAPIException(
                f"Unexpected error fetching from arXiv: {e}"
            ) from e

    # --- Public fetch methods ---

    async def fetch_papers(
        self,
        max_results: Optional[int] = None,
        start: int = 0,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> List[ArxivPaper]:
        """
        Fetch papers from arXiv for the configured category.

        This is the main method used by the DAG every morning.
        It fetches the latest papers in the configured category
        (e.g. cs.AI) optionally filtered by date range.

        Args:
            max_results: How many papers to fetch.
                         Defaults to settings value if not given.
                         Capped at 2000 (arXiv API limit).
            start:       Pagination offset. 0 = first page.
            sort_by:     How to sort results. Options:
                           "submittedDate"   — newest first (default)
                           "lastUpdatedDate" — recently updated first
                           "relevance"       — most relevant first
            sort_order:  "descending" (default) or "ascending"
            from_date:   Only fetch papers submitted after this date.
                         Format: YYYYMMDD (e.g. "20240101")
            to_date:     Only fetch papers submitted before this date.
                         Format: YYYYMMDD (e.g. "20240131")

        Returns:
            List of ArxivPaper objects

        Example:
            # Fetch up to 50 cs.AI papers from January 2024
            papers = await client.fetch_papers(
                max_results=50,
                from_date="20240101",
                to_date="20240131",
            )
        """
        if max_results is None:
            max_results = self.max_results

        # Start with the category filter (always applied)
        # Example: "cat:cs.AI"
        search_query = f"cat:{self.search_category}"

        # Add date range if either date is provided
        # arXiv date format requires YYYYMMDDHHMM
        # We use 0000 for start of day, 2359 for end of day
        # * means "no limit" on that side
        if from_date or to_date:
            date_from = f"{from_date}0000" if from_date else "*"
            date_to = f"{to_date}2359" if to_date else "*"
            search_query += f" AND submittedDate:[{date_from}+TO+{date_to}]"

        params = {
            "search_query": search_query,
            "start": start,
            "max_results": min(max_results, 2000),  # arXiv hard limit is 2000
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        # Note: safe=":+[]" — these characters must NOT be URL-encoded
        # because arXiv's API reads them literally in search queries
        url = self._build_url(params, safe=":+[]")

        logger.info(
            f"Fetching up to {max_results} papers "
            f"from category '{self.search_category}'"
        )

        # _get() handles rate limiting, timeout, and HTTP errors
        xml_data = await self._get(url)
        papers = self._parser.parse(xml_data)

        logger.info(f"Fetched {len(papers)} papers")
        return papers

    async def fetch_papers_with_query(
        self,
        search_query: str,
        max_results: Optional[int] = None,
        start: int = 0,
        sort_by: str = "submittedDate",
        sort_order: str = "descending",
    ) -> List[ArxivPaper]:
        """
        Fetch papers using a custom arXiv search query.

        Use this when fetch_papers() isn't flexible enough —
        for example, searching by author, title keyword,
        or combining multiple filters.

        Args:
            search_query: Full arXiv query string. Examples:
                "au:LeCun AND cat:cs.AI"         ← by author
                "ti:transformer AND cat:cs.AI"   ← by title keyword
                "cat:cs.AI AND cat:cs.LG"        ← multiple categories
            max_results:  How many papers to fetch (default from settings)
            start:        Pagination offset
            sort_by:      "submittedDate", "lastUpdatedDate", or "relevance"
            sort_order:   "descending" or "ascending"

        Returns:
            List of ArxivPaper objects matching the query
        """
        if max_results is None:
            max_results = self.max_results

        params = {
            "search_query": search_query,
            "start": start,
            "max_results": min(max_results, 2000),
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        # Note: safe includes "*" here because custom queries
        # may use wildcard searches (e.g. "ti:transform*")
        # fetch_papers() doesn't need "*" since it builds its
        # own controlled query without wildcards
        url = self._build_url(params, safe=":+[]*")

        logger.info(f"Fetching papers with custom query: '{search_query}'")

        xml_data = await self._get(url)
        papers = self._parser.parse(xml_data)

        logger.info(f"Query returned {len(papers)} papers")
        return papers

    async def fetch_paper_by_id(self, arxiv_id: str) -> Optional[ArxivPaper]:
        """
        Fetch one specific paper by its arXiv ID.

        Use this when you already know the paper ID and
        just need to look it up.

        Args:
            arxiv_id: arXiv paper ID. Can include version or not:
                "2507.17748"    ← without version (recommended)
                "2507.17748v1"  ← with version (version is stripped)

        Returns:
            ArxivPaper object if found, None if not found

        Example:
            paper = await client.fetch_paper_by_id("2507.17748")
            if paper:
                print(paper.title)
        """
        # Strip version number if present — arXiv search works
        # better without it and returns the latest version
        # "2507.17748v1" → "2507.17748"
        clean_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id

        params = {
            "id_list": clean_id,
            "max_results": 1,
        }

        # FIX: original code had no timeout here — could hang forever.
        # Now using _get() which always applies self.timeout_seconds.
        url = self._build_url(params, safe=":+[]*")

        logger.info(f"Fetching paper by ID: {clean_id}")

        xml_data = await self._get(url)
        papers = self._parser.parse(xml_data)

        if papers:
            return papers[0]

        logger.warning(f"Paper not found: {arxiv_id}")
        return None

    # --- PDF Download ---
    async def download_pdf(
        self,
        paper: ArxivPaper,
        force_download: bool = False,
    ) -> Optional[Path]:
        """
        Download a paper's PDF to local cache.

        Checks if the PDF is already downloaded before
        hitting the network — skips download if cached.

        Args:
            paper:          The paper to download
            force_download: If True, re-download even if
                            the file already exists locally

        Returns:
            Path to the PDF file if successful, None if failed
        """
        if not paper.pdf_url:
            logger.error(f"No PDF URL for paper {paper.arxiv_id}")
            return None

        pdf_path = self._get_pdf_path(paper.arxiv_id)

        # Use cached file if it exists and we're not forcing a re-download
        if pdf_path.exists() and not force_download:
            logger.info(f"Using cached PDF: {pdf_path.name}")
            return pdf_path

        logger.info(f"Downloading PDF for paper {paper.arxiv_id}")

        if await self._download_with_retry(paper.pdf_url, pdf_path):
            return pdf_path

        return None

    def _get_pdf_path(self, arxiv_id: str) -> Path:
        """
        Build the local file path for a paper's PDF.

        Replaces "/" in IDs with "_" to make a safe filename.
        Example: "2507.17748v1" → "2507.17748v1.pdf"

        Args:
            arxiv_id: arXiv paper ID

        Returns:
            Full Path object pointing to where the PDF should live
        """
        safe_filename = arxiv_id.replace("/", "_") + ".pdf"
        return self.pdf_cache_dir / safe_filename

    async def _download_with_retry(
        self,
        url: str,
        path: Path,
        max_retries: Optional[int] = None,
    ) -> bool:
        """
        Download a file with automatic retry on failure.

        Tries up to max_retries times. Waits longer between
        each failed attempt (linear backoff: 1×, 2×, 3× delay).

        FIX: Original code had three bugs here:
        1. Always slept the full rate_limit_delay even if enough
           time had passed — now uses _apply_rate_limit() instead
        2. Partial files weren't cleaned up on timeout
           — now uses try/finally to always clean up
        3. Comment said "exponential backoff" but math was linear
           — comment now matches the actual behavior

        Args:
            url:         URL to download from
            path:        Local file path to save to
            max_retries: How many attempts before giving up
                         (defaults to settings value)

        Returns:
            True if download succeeded, False if all retries failed
        """
        if max_retries is None:
            max_retries = self._settings.download_max_retries

        logger.info(f"Downloading PDF from {url}")

        # Respect arXiv rate limits before downloading
        # FIX: use _apply_rate_limit() instead of unconditional sleep
        await self._apply_rate_limit()

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
                    async with client.stream("GET", url) as response:
                        response.raise_for_status()

                        # FIX: wrap file write in try/finally so partial
                        # downloads are always cleaned up if something fails
                        try:
                            with open(path, "wb") as f:
                                async for chunk in response.aiter_bytes():
                                    f.write(chunk)
                        except Exception:
                            # Delete partial file before re-raising
                            if path.exists():
                                path.unlink()
                                logger.warning(f"Deleted partial download: {path.name}")
                            raise

                logger.info(f"Successfully downloaded to {path.name}")
                return True

            except httpx.TimeoutException as e:
                # Linear backoff: wait 1× delay on attempt 1,
                # 2× on attempt 2, 3× on attempt 3, etc.
                # FIX: comment now matches actual math (was "exponential")
                wait_time = self._settings.download_retry_delay_base * (attempt + 1)

                if attempt < max_retries - 1:
                    logger.warning(
                        f"Timeout on attempt {attempt + 1}/{max_retries}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Download timed out after {max_retries} attempts")
                    raise PDFDownloadTimeoutError(
                        f"PDF download timed out after {max_retries} attempts: {e}"
                    ) from e

            except httpx.HTTPError as e:
                wait_time = self._settings.download_retry_delay_base * (attempt + 1)

                if attempt < max_retries - 1:
                    logger.warning(
                        f"HTTP error on attempt {attempt + 1}/{max_retries}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Download failed after {max_retries} attempts: {e}")
                    raise PDFDownloadException(
                        f"PDF download failed after {max_retries} attempts: {e}"
                    ) from e

            except Exception as e:
                # Unexpected error — don't retry, fail immediately
                logger.error(f"Unexpected download error: {e}")
                raise PDFDownloadException(
                    f"Unexpected error during PDF download: {e}"
                ) from e

        return False