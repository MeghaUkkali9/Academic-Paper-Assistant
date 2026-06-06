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

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from functools import cached_property
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote, urlencode

import httpx

from src.config import ArxivSettings
from src.exceptions import (
    ArxivAPIException,
    ArxivAPITimeoutError,
    ArxivParseError,
    PDFDownloadException,
    PDFDownloadTimeoutError,
)
from src.schemas.arxiv.paper import ArxivPaper

logger = logging.getLogger(__name__)


class ArxivClient:
    """
    Client for fetching papers from the arXiv API.

    Handles:
    - Rate limiting (arXiv recommends 3 seconds between requests)
    - XML parsing of API responses
    - PDF downloading with retry logic

    Usage:
        client = ArxivClient(settings=settings.arxiv)
        papers = await client.fetch_papers(max_results=50)
    """

    def __init__(self, settings: ArxivSettings):
        self._settings = settings
        self._last_request_time: Optional[float] = None

        # Add a lock so concurrent requests don't both fire
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