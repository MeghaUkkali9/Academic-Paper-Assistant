import requests
import psycopg2
import logging

from airflow import DAG
from airflow.operators.python import PythonOperator, BashOperator
from datetime import datetime, timedelta
from .setup import pre_flight_checks
from .fetch_process_store_papers import fetch_process_store_papers_in_db
from .index_papers import index_papers

logger = logging.getLogger(__name__)

def pre_flight_check():
    logger.info("Running pre-flight checks...")
    return pre_flight_checks()

def fetch_process_store_papers():
    logger.info("Fetching papers from arXiv API...")
    return fetch_process_store_papers_in_db()

def index_papers_in_opensearch():
    logger.info("Indexing papers in OpenSearch...")
    return index_papers()

def generate_report():
    logger.info("Generating report...")
    return "Report generated successfully"

with DAG(
    'arxiv_paper_etl',
    default_args={
        'owner': 'airflow',
        'depends_on_past': False,
        'start_date': datetime(2024, 1, 1),
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    schedule_interval='@daily',
    catchup=False
) as dag:
    
    pre_flight_task = PythonOperator(
        task_id='pre_flight_checks',
        python_callable=pre_flight_check
    )
        
    fetch_process_store_papers_task = PythonOperator(
        task_id='fetch_process_store_papers',
        python_callable=fetch_process_store_papers
    )
    
    index_papers_in_opensearch_task = PythonOperator(
        task_id='index_papers_in_opensearch',
        python_callable=index_papers_in_opensearch
    )
    
    generate_report_task = PythonOperator(
        task_id='generate_report',
        python_callable=generate_report
    )
    
    cleanup_task = BashOperator(
        task_id='cleanup',
        bash_command='echo "Cleaning up resources..."'
    )
    
    pre_flight_task >> fetch_process_store_papers_task >> index_papers_in_opensearch_task >> generate_report_task