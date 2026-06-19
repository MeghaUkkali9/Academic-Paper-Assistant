from pathlib import Path
from typing import Optional
from src.config import Settings
from src.services.arxiv.client import ArxivClient
from src.services.pdf_parser.parser import PDFParserService
from .metadata_fetcher import MetadataFetcher
from src.config import get_settings

def make_metadata_fetcher(
    arxiv_client: ArxivClient,
    pdf_parser: PDFParserService,
    pdf_cache_dir: Optional[Path] = None,
    settings: Optional[Settings] = None,
) -> MetadataFetcher:
    """Create MetadataFetcher instance with configuration settings."""
    
    if settings is None:
        settings = get_settings()

    return MetadataFetcher(
        arxiv_client=arxiv_client,
        pdf_parser=pdf_parser,
        pdf_cache_dir=pdf_cache_dir,
        max_concurrent_downloads=settings.arxiv.max_concurrent_downloads,
        max_concurrent_parsing=settings.arxiv.max_concurrent_parsing,
        settings=settings,
    )