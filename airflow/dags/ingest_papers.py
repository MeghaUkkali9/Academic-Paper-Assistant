import asyncio
import logging
from datetime import datetime, timedelta
from .common import get_cached_services

logger = logging.getLogger(__name__)

async def run_paper_ingestion_pipeline(
    target_date: str
) -> dict:
    """Async wrapper for the paper ingestion pipeline"""
    arxiv_client, _, database, paper_fetcher, _ = get_cached_services()
    
    with database.get_session() as session:
        return await paper_fetcher.process_papers(
            from_date=target_date,
            to_date=target_date,
            db_session=session,
        )

def ingest_papers(**context):
    """Fetch daily papers from arXiv and store in PostgreSQL.

    This task:
    1. Determines the target date (defaults to yesterday)
    2. Fetches papers from arXiv API
    3. Downloads and processes PDFs using Docling
    4. Stores metadata and parsed content in PostgreSQL
    """
    logger.info("Starting daily paper fetching task")

    execution_date = context.get("execution_date")
    if execution_date:
        target_dt = execution_date - timedelta(days=1)
        target_date = target_dt.strftime("%Y%m%d")
    else:
        yesterday = datetime.now() - timedelta(days=1)
        target_date = yesterday.strftime("%Y%m%d")

    logger.info(f"Fetching papers for date: {target_date}")

    results = asyncio.run(
        run_paper_ingestion_pipeline(
            target_date=target_date
        )
    )

    logger.info(f"Daily fetch complete: {results['papers_fetched']} papers for {target_date}")

    results["date"] = target_date
    ti = context.get("ti")
    if ti:
        ti.xcom_push(key="fetch_results", value=results)

    return results
#todo:
# get papers from the arxiv client with retry logic and error handling
# transform papers into the format expecetd by the database client
# process papers in batches to avoid memory issues and optimize database writes
# implement logging at each step to track progress and catch issues
# ensure idempotency: if the same paper is ingested multiple times,
# it should not create duplicates in the database
# handle edge cases, such as missing fields in the arXiv data, or papers that fail to parse
# consider adding metrics (e.g. number of papers ingested, time taken) for monitoring and alerting
# overall, this function should reliably fetch the latest papers from arXiv,
# transform them as needed, and then efficiently and safely
# store papers in the database.
