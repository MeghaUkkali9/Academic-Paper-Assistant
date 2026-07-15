import logging
import sys
from functools import lru_cache

sys.path.insert(0, "/opt/airflow")

logger = logging.getLogger(__name__)

"""
IMPORTANT ABOUT CACHING:
Each getter below is cached with lru_cache, scoped to this process.
Airflow runs each task in a separate process, so this cache does NOT
persist between DAG tasks.

Services are initialized lazily and individually so that a task only
pays the initialization cost (e.g. loading Docling's models) for the
services it actually uses, instead of every task eagerly initializing
every service.
"""


@lru_cache(maxsize=1)
def get_database():
    from src.database.factory import create_database

    try:
        database = create_database()
        logger.info("Database initialized")
        return database
    except Exception as e:
        raise Exception("Failed to initialize database") from e


@lru_cache(maxsize=1)
def get_arxiv_client():
    from src.services.arxiv.factory import make_arxiv_client

    try:
        arxiv_client = make_arxiv_client()
        logger.info("arXiv client initialized")
        return arxiv_client
    except Exception as e:
        raise Exception("Failed to initialize arXiv client") from e


@lru_cache(maxsize=1)
def get_pdf_parser():
    from src.services.pdf_parser.factory import make_pdf_parser_service

    try:
        pdf_parser = make_pdf_parser_service()
        logger.info("PDF parser initialized")
        return pdf_parser
    except Exception as e:
        raise Exception("Failed to initialize PDF parser") from e


@lru_cache(maxsize=1)
def get_opensearch_client():
    from src.services.opensearch.factory import (
        get_opensearch_client as _make_opensearch_client,
    )

    try:
        opensearch_client = _make_opensearch_client()
        logger.info("OpenSearch client initialized")
        return opensearch_client
    except Exception as e:
        raise Exception("Failed to initialize OpenSearch client") from e


@lru_cache(maxsize=1)
def get_paper_fetcher():
    from src.services.paper_metadata_pipeline.factory import create_paper_fetcher

    try:
        paper_fetcher = create_paper_fetcher(get_arxiv_client(), get_pdf_parser())
        logger.info("Metadata fetcher initialized")
        return paper_fetcher
    except Exception as e:
        raise Exception("Failed to initialize metadata fetcher") from e
