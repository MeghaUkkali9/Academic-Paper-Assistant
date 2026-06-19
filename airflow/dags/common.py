import logging
import sys
from functools import lru_cache
from typing import NamedTuple

sys.path.insert(0, "/opt/airflow")

from src.database.factory import create_database
from src.services.arxiv.factory import make_arxiv_client
from src.services.paper_metadata_pipeline.factory import make_metadata_fetcher
from src.services.opensearch.factory import make_opensearch_client
from src.services.pdf_parser.factory import make_pdf_parser_service

logger = logging.getLogger(__name__)

# NamedTuple gives both dot access AND tuple unpacking,
# so existing code that unpacks it still works.
class Services(NamedTuple):
    """
    Container for all initialized service instances.

    Using NamedTuple means:
    - You can access by name:  services.database
    - You can still unpack:    arxiv, pdf, db, meta, os = services
    - The order is documented here in one place
    """
    arxiv_client: object
    pdf_parser: object
    database: object
    metadata_fetcher: object
    opensearch_client: object


@lru_cache(maxsize=1)
def get_cached_services() -> Services:
    """
    Initialize all services and cache them for the lifetime
    of this process.

    IMPORTANT ABOUT CACHING:
    lru_cache stores results in memory, inside one process.
    Airflow runs each task in a separate process, so this
    cache does NOT persist between DAG tasks.

    What it DOES help with:
    If multiple functions inside the same task call
    get_cached_services(), they all get the same objects
    back without re-initializing anything.

    Returns:
        Services namedtuple containing all initialized services
    
    Raises:
        Exception: if any individual service fails to initialize,
                   with a clear message about which one failed
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
        database = create_database()
        logger.info("Database initialized")
    except Exception as e:
        raise Exception("Failed to initialize database") from e

    try:
        opensearch_client = make_opensearch_client()
        logger.info("OpenSearch client initialized")
    except Exception as e:
        raise Exception("Failed to initialize OpenSearch client") from e

    try:
        metadata_fetcher = make_metadata_fetcher(arxiv_client, pdf_parser)
        logger.info("Metadata fetcher initialized")
    except Exception as e:
        raise Exception("Failed to initialize metadata fetcher") from e

    logger.info("All services initialized and cached")

    return Services(
        arxiv_client=arxiv_client,
        pdf_parser=pdf_parser,
        database=database,
        metadata_fetcher=metadata_fetcher,
        opensearch_client=opensearch_client,
    )