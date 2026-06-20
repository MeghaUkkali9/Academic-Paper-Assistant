import logging

from src.config import get_settings
from .client import ArxivClient

logger = logging.getLogger(__name__)


def make_arxiv_client() -> ArxivClient:
    """
    Create and return an ArxivClient using the current settings.
    """
    settings = get_settings()

    if not settings.arxiv:
        raise ValueError(
            "ArxivClient config missing — check your settings for [arxiv] section"
        )

    logger.info("Creating ArxivClient")
    return ArxivClient(settings=settings.arxiv)