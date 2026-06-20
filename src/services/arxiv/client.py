import time
import asyncio
import httpx
import logging
from pathlib import Path
from urllib.parse import urlencode, quote
from functools import cached_property
from typing import List, Optional

from src.config import ArxivSettings
from src.schemas.arxiv.researchpaper import ArxivResearchPaper
from src.services.arxiv.xml_parser import ArxivXmlParser
from src.exceptions import (
    ArxivAPIException, 
    ArxivAPITimeoutError, 
    PDFDownloadException, 
    PDFDownloadTimeoutError)


logger = logging.getLogger(__name__)

class ArxivClient:
    def __init__(self, settings: ArxivSettings):
        self._settings = settings
        self._last_request_time: Optional[float] = None
        self._parser = ArxivXmlParser(namespaces=settings.namespaces)
        self._rate_limit_lock = asyncio.Lock()
    
    async def _apply_rate_limit(self) -> None:
        async with self._rate_limit_lock:

            if self._last_request_time is not None:
                elapsed = time.monotonic() - self._last_request_time

                remaining = self._settings.rate_limit_delay - elapsed

                if remaining > 0:
                    logger.debug(f"Rate limit active, sleeping {remaining:.2f}s")
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
        
        url = f"{self._settings.base_url}?{urlencode(params, quote_via=quote, safe=':+[]')}"

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
    
    @cached_property
    def pdf_cache_dir(self) -> Path:
        cache_dir = Path(self._settings.pdf_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _get_pdf_path(
        self, 
        arxiv_id: str
    ) -> Path:
        
        safe_filename = arxiv_id.replace("/", "_") + ".pdf"
        return self.pdf_cache_dir / safe_filename
    
    async def download_pdf(
        self,
        paper: ArxivResearchPaper
    ) -> Optional[Path]:
        
        if not paper.pdf_url:
            logger.error(f"PDF URL not found {paper.arxiv_id}")
            return None

        pdf_path = self._get_pdf_path(paper.arxiv_id)

        if pdf_path.exists():
            logger.info(f"cached PDF: {pdf_path.name}")
            return pdf_path

        if await self._download_pdf_with_retry(paper.pdf_url, pdf_path):
            return pdf_path

        return None
    
    def _cleanup_partial_download(
        self,
        pdf_path: Path,
    ) -> None:
        try:
            if pdf_path.exists():
                pdf_path.unlink()
                logger.warning(f"Deleted partial download: {pdf_path.name}")
        except Exception as e:
            logger.error(f"Failed to cleanup partial file {pdf_path}: {e}")
            
    async def _download_pdf_with_retry(
        self,
        pdf_url: str,
        pdf_path: Path,
    ) -> bool:
        logger.info(f"Downloading PDF from {pdf_url}")
        
        max_retries = self._settings.download_max_retries

        for attempt in range(max_retries):
            
            await self._apply_rate_limit()
            
            try:
                async with httpx.AsyncClient(timeout=float(self._settings.timeout_seconds)) as client:
                    async with client.stream("GET", pdf_url) as response:
                        response.raise_for_status()

                        with open(pdf_path, "wb") as file:
                            async for chunk in response.aiter_bytes():
                                file.write(chunk)

                logger.info(f"Successfully downloaded to {pdf_path.name}")
                return True

            except httpx.TimeoutException as e:
                self._cleanup_partial_download(pdf_path=pdf_path)
                
                wait_time = self._settings.download_retry_delay_base * (attempt + 1)

                if attempt < max_retries - 1:
                    logger.warning(
                        f"Timeout on attempt {attempt + 1}/{max_retries}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.exception(f"Download timed out after {max_retries} attempts")
                    raise PDFDownloadTimeoutError(f"PDF download timed out after {max_retries} attempts: {e}")

            except httpx.HTTPError as e:
                self._cleanup_partial_download(pdf_path=pdf_path)
                
                wait_time = self._settings.download_retry_delay_base * (attempt + 1)

                if attempt < max_retries - 1:
                    logger.warning(
                        f"HTTP error on attempt {attempt + 1}/{max_retries}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.exception(f"Download failed after {max_retries} attempts")
                    raise PDFDownloadException(f"PDF download failed after {max_retries} attempts: {e}")

            except Exception as e:
                self._cleanup_partial_download(pdf_path=pdf_path)
                
                logger.exception("Unexpected error occurred while downloading")
                raise PDFDownloadException(f"Unexpected error during PDF download: {e}")

        return False
    
    