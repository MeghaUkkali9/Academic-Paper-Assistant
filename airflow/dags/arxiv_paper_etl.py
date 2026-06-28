# dag.py
#
# PURPOSE: Define the arXiv paper ingestion pipeline.
# Runs daily: pre-flight → fetch → index → report → cleanup
#
# SCHEDULE: scheduled to run every weekday at 4am UTC, but can be triggered manually as needed on airflow UI.
# To run manually: airflow dags trigger arxiv_paper_etl

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

from src.airflow_tasks.setup import setup_environment
from src.airflow_tasks.ingest_papers import ingest_papers
from src.airflow_tasks.index_papers import index_research_papers
from src.airflow_tasks.reporting import generate_report

logger = logging.getLogger(__name__)

# --- DAG definition ---
with DAG(
    dag_id="arxiv_paper_etl",
    description="Daily ETL pipeline for ingesting and indexing arXiv research papers",
    default_args={
        "owner": "megha_ukkali_research_paper",
        "depends_on_past": False,
        "start_date": datetime(2025, 10, 10),
        "retries": 3,
        "retry_delay": timedelta(minutes=30),
        "email_on_failure": False,
        "email_on_retry": False,
    },
    schedule="0 4 * * 1-5",
    catchup=False,
    max_active_runs=1,
    tags=["arxiv", "papers", "ingestion", "hybrid-search"],
) as dag:

    # Step 1: Verify database + OpenSearch are alive
    setup_environment_task = PythonOperator(
        task_id="setup_environment",
        python_callable=setup_environment,
    )

    # Step 2: Fetch papers from arXiv, process, and store in PostgreSQL
    ingest_papers_task = PythonOperator(
        task_id="ingest_papers",
        python_callable=ingest_papers,
    )

    # Step 3: Index stored papers in OpenSearch for hybrid search
    index_papers_task = PythonOperator(
        task_id="index_papers",
        python_callable=index_research_papers,
    )

    # Step 4: Generate a summary report of what was ingested
    generate_daily_report_task = PythonOperator(
        task_id="generate_report",
        python_callable=generate_report,
    )

    # Step 5: Clean up temp files older than 30 days
    cleanup_task = BashOperator(
        task_id="cleanup",
        bash_command="""
            echo "Cleaning up temporary files..."
            find /tmp -name "*.pdf" -type f -mtime +30 -delete 2>/dev/null || true
            echo "Cleanup completed"
        """,
    )

    # Pipeline order — each step runs only if the previous one succeeded
    setup_environment_task >> ingest_papers_task >> index_papers_task >> generate_daily_report_task >> cleanup_task