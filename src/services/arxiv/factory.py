# factory.py
#
# PURPOSE: Create an ArxivClient with the correct settings.
# Called by common.py when initializing all services.

import logging

from src.config import get_settings
from .client import ArxivClient

logger = logging.getLogger(__name__)


def make_arxiv_client() -> ArxivClient:
    """
    Create and return an ArxivClient using the current settings.

    Settings come from the centralized config (get_settings),
    which reads from environment variables or config files.

    Returns:
        ArxivClient instance ready to fetch papers

    Raises:
        ValueError: if arxiv settings are missing from config
    """
    settings = get_settings()

    if not settings.arxiv:
        raise ValueError(
            "ArxivClient config missing — check your settings for [arxiv] section"
        )

    logger.info("Creating ArxivClient")
    return ArxivClient(settings=settings.arxiv)