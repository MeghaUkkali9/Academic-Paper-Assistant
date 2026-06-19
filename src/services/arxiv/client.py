import httpx
import logging
import time
import asyncio
from pathlib import Path
from urllib.parse import urlencode, quote
from functools import cached_property
from typing import List, Optional
from src.config import ArxivSettings
from src.exceptions import (ArxivAPIException, ArxivAPITimeoutError, PDFDownloadException, PDFDownloadTimeoutError)
from src.schemas.arxiv.researchpaper import ArxivResearchPaper
from src.services.arxiv.xml_parser import ArxivXmlParser

logger = logging.getLogger(__name__)

class ArxivClient:
    def __init__(self, settings: ArxivSettings):
        self._settings = settings
        self._last_request_time: Optional[float] = None
        self._parser = ArxivXmlParser(namespaces=settings.namespaces)
        self._rate_limit_lock = asyncio.Lock()
        
    @cached_property
    def pdf_cache_dir(self) -> Path:
       
        cache_dir = Path(self._settings.pdf_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    async def download_pdf(
        self,
        paper: ArxivResearchPaper,
        force_download: bool = False,
    ) -> Optional[Path]:
        if not paper.pdf_url:
            logger.error(f"No PDF URL for paper {paper.arxiv_id}")
            return None

        pdf_path = self._get_pdf_path(paper.arxiv_id)

        if pdf_path.exists() and not force_download:
            logger.info(f"Using cached PDF: {pdf_path.name}")
            return pdf_path

        logger.info(f"Downloading PDF for paper {paper.arxiv_id}")

        if await self._download_with_retry(paper.pdf_url, pdf_path):
            return pdf_path

        return None

    def _get_pdf_path(self, arxiv_id: str) -> Path:
        safe_filename = arxiv_id.replace("/", "_") + ".pdf"
        return self.pdf_cache_dir / safe_filename

    async def _download_with_retry(
        self,
        url: str,
        path: Path,
        max_retries: Optional[int] = None,
    ) -> bool:
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
    
    async def _apply_rate_limit(self) -> None:
        async with self._rate_limit_lock:

            if self._last_request_time is not None:
                elapsed = time.monotonic() - self._last_request_time

                remaining = self._settings.rate_limit_delay - elapsed

                if remaining > 0:
                    print(f"Sleeping {remaining:.2f}s")
                    await asyncio.sleep(remaining)

            self._last_request_time = time.monotonic()
            
    async def fetch_research_papers(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        ) -> List[ArxivResearchPaper]:
        
        search_query = f"cat:{self._settings.search_category}"
        if from_date or to_date:
            date_from = f"{from_date}0000" if from_date else "*"
            date_to = f"{to_date}2359" if to_date else "*"
            search_query += f" AND submittedDate:[{date_from}+TO+{date_to}]"

        params = {
                "search_query": search_query,
                "start": 0,
                "max_results": self._settings.max_papers,
                "sortBy": self._settings.sort_by,
                "sortOrder": self._settings.sort_order,
            }
        
        url = f"{self._settings.base_url}?{urlencode(params, quote_via=quote, safe=":+[]")}"

        logger.info(f"Fetching {self._settings.max_papers} papers from category {self._settings.search_category}")
        
        await self._apply_rate_limit()
        try:
            async with httpx.AsyncClient(timeout=60) as httpclient:
                response = await httpclient.get(url)
                response.raise_for_status()
                
                xml_data = response.text
                return self._parser.parse(xml_data=xml_data)
            
        except httpx.TimeoutException as te:
            logger.exception("Timeout while calling arXiv API")
            raise ArxivAPITimeoutError(f"arXiv API request timed out: {te}")

        except httpx.HTTPStatusError as httpstatuserrror:
            logger.exception("arXiv API returned an error response")
            raise ArxivAPIException(f"arXiv API returned error {httpstatuserrror.response.status_code}: {httpstatuserrror}")

        except Exception as e:
            logger.exception("Unexpected error occurred while calling arXiv API")
            raise ArxivAPIException(f"Unexpected error fetching from arXiv : {e}")
    