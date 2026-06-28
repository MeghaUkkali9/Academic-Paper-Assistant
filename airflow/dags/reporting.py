import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_report(**context):
    """
    Generate a summary report for the current pipeline execution.

    This task:
    - Collects ingestion statistics from XCom.
    - Collects indexing statistics from XCom.
    - Determines the overall pipeline status.
    - Logs and returns the report.
    """

    logger.info("Generating pipeline execution report.")

    task_instance = context.get("ti")

    if task_instance is None:
        logger.warning("Task instance not available.")
        return {}

    ingestion_result = (
        task_instance.xcom_pull(
            task_ids="ingest_papers",
            key="ingestion_result",
        )
        or {}
    )

    indexing_result = (
        task_instance.xcom_pull(
            task_ids="index_papers",
            key="indexing_result",
        )
        or {}
    )

    pipeline_status = "SUCCESS"

    if (
        ingestion_result.get("papers_failed", 0) > 0
        or indexing_result.get("papers_failed", 0) > 0
        or indexing_result.get("chunks_indexing_failed", 0) > 0
    ):
        pipeline_status = "PARTIAL_SUCCESS"

    report = {
        "execution_date": context.get("logical_date", datetime.utcnow()).isoformat(),
        "pipeline_status": pipeline_status,
        "ingestion_statistics": ingestion_result,
        "indexing_statistics": indexing_result,
    }

    logger.info("=" * 70)
    logger.info("Academic Paper Pipeline Report")
    logger.info("=" * 70)

    logger.info("Execution Date : %s", report["execution_date"])
    logger.info("Pipeline Status: %s", report["pipeline_status"])

    logger.info("")
    logger.info("Ingestion Statistics")
    logger.info("--------------------")
    logger.info(
        "Papers fetched  : %d",
        ingestion_result.get("papers_fetched", 0),
    )
    logger.info(
        "Papers parsed   : %d",
        ingestion_result.get("papers_parsed", 0),
    )
    logger.info(
        "Papers stored   : %d",
        ingestion_result.get("papers_stored", 0),
    )
    logger.info(
        "Papers skipped  : %d",
        ingestion_result.get("papers_skipped", 0),
    )
    logger.info(
        "Papers failed   : %d",
        ingestion_result.get("papers_failed", 0),
    )

    logger.info("")
    logger.info("Indexing Statistics")
    logger.info("-------------------")
    logger.info(
        "Papers processed      : %d",
        indexing_result.get("papers_processed", 0),
    )
    logger.info(
        "Chunks created        : %d",
        indexing_result.get("chunks_created", 0),
    )
    logger.info(
        "Embeddings generated  : %d",
        indexing_result.get("embeddings_generated", 0),
    )
    logger.info(
        "Chunks indexed        : %d",
        indexing_result.get("chunks_indexed", 0),
    )
    logger.info(
        "Chunk indexing failed : %d",
        indexing_result.get("chunks_indexing_failed", 0),
    )

    logger.info("=" * 70)

    task_instance.xcom_push(
        key="daily_report",
        value=report,
    )

    return report