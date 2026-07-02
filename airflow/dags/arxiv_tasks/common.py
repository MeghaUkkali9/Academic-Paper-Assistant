import logging
import sys
from functools import lru_cache
from typing import NamedTuple

sys.path.insert(0, "/opt/airflow")

from src.database.factory import create_database
from src.services.arxiv.factory import make_arxiv_client
from src.services.paper_metadata_pipeline.factory import create_paper_fetcher
from src.services.opensearch.factory import get_opensearch_client
from src.services.pdf_parser.factory import make_pdf_parser_service

logger = logging.getLogger(__name__)

class Services(NamedTuple):
    """
    Container for all initialized service instances.
    """
    arxiv_client: object
    pdf_parser: object
    database: object
    paper_fetcher: object
    opensearch_client: object


@lru_cache(maxsize=1)
def get_services() -> Services:
    """
    Initialize all services and cache them for the lifetime
    of this process.

    IMPORTANT ABOUT CACHING:
    lru_cache stores results in memory, inside one process.
    Airflow runs each task in a separate process, so this
    cache does NOT persist between DAG tasks.

    What it DOES help with:
    If multiple functions inside the same task call
    get_services(), they all get the same objects
    back without re-initializing anything.
    """
    logger.info("Initializing services for this process")

    
    try:
        arxiv_client = make_arxiv_client()
        logger.info("arXiv client initialized")
    except Exception as e:
        raise Exception("Failed to initialize arXiv client") from e

    try:
        pdf_parser = make_pdf_parser_service()
        logger.info("PDF parser initialized")
    except Exception as e:
        raise Exception("Failed to initialize PDF parser") from e

    try:
        paper_fetcher = create_paper_fetcher(arxiv_client, pdf_parser)
        logger.info("Metadata fetcher initialized")
    except Exception as e:
        raise Exception("Failed to initialize metadata fetcher") from e
    
    try:
        database = create_database()
        logger.info("Database initialized")
    except Exception as e:
        raise Exception("Failed to initialize database") from e

    try:
        opensearch_client = get_opensearch_client()
        logger.info("OpenSearch client initialized")
    except Exception as e:
        raise Exception("Failed to initialize OpenSearch client") from e

    logger.info("All services initialized and cached")

    return Services(
        arxiv_client=arxiv_client,
        pdf_parser=pdf_parser,
        database=database,
        paper_fetcher=paper_fetcher,
        opensearch_client=opensearch_client,
    )