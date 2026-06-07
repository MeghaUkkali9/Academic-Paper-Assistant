import logging
from sqlalchemy import text
from .common import get_cached_services

# setup.py
#
# PURPOSE: Pre-flight checks before the DAG runs.
# Verifies database + OpenSearch are alive, and creates
# the search index + RRF pipeline if they don't exist yet.

logger = logging.getLogger(__name__)

def _check_database_connection(database) -> None:
    """
    Verify the database is reachable.

    Runs the simplest possible query — if it doesn't crash,
    the database is alive.

    Raises:
        Exception: if the database connection fails
    """
    with database.get_session() as session:
        session.execute(text("SELECT 1"))
        
    logger.info("Database connection successful.")
    
def _check_opensearch_connection(opensearch_client) -> None:
    """
    Verify OpenSearch is reachable and healthy.

    Green = fully healthy
    Yellow = healthy but some replicas missing (still usable)
    Red = primary shards missing — data loss risk, do NOT proceed

    Raises:
        Exception: if OpenSearch is unreachable or status is red
    """
    try:
        health = opensearch_client.cluster.health()
    
        status = health.get("status")
        if status == "red":
            raise Exception("OpenSearch cluster status is RED. Do not proceed.")
        elif status in ["yellow", "green"]:
            logger.info(f"OpenSearch cluster status is {status.upper()}. Connection successful.")
        else:
            raise Exception(f"Unexpected OpenSearch cluster status: {status}")
    except Exception as e:
        logger.error(f"Error connecting to OpenSearch: {str(e)}")   
        raise Exception(f"Failed to connect to OpenSearch: {str(e)}")

def _setup_search_indices(opensearch_client) -> None:
    """
    Create the hybrid search index and RRF pipeline if they
    don't already exist.

    force=False means: skip creation if already exists.
    """
    result = opensearch_client.setup_indices(force=False)
    
    if result.get("hybrid_index"):
        logger.info("hybrid index created.")
    else:
        logger.info("hybrid index already exists, skipping creation.")
        
    if result.get("rrf_pipeline"):
        logger.info("RRF pipeline created.")
    else:
        logger.info("RRF pipeline already exists, skipping creation.")  
        
def setup_environment() -> dict:
    """
    Main entry point — called by Airflow as the first DAG task.

    Runs three checks in order:
        1. Database reachable?
        2. OpenSearch reachable and healthy?
        3. Search index + pipeline exist (create if not)?

    Returns:
        dict with status and message on success

    Raises:
        Exception: if any check fails (stops the entire DAG)
    """
    
    logger.info("Starting pre-flight checks...")
    
    # NOTE: get_cached_services() initializes ALL services even though
    # we only use database and opensearch_client here. This is intentional
    # — it warms the cache for the tasks that run after this one.
    _, _, database, _, opensearch_client = get_cached_services()
    
    _check_database_connection(database)
    _check_opensearch_connection(opensearch_client)
    _setup_search_indices(opensearch_client) 
    
    logger.info("Pre-flight checks completed successfully.")    
    
    return {
        "status": "success", 
        "message": "setup checks passed."
    } 