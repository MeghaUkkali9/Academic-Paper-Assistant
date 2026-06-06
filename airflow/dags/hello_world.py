from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import requests
import psycopg2

def print_hello():
    print("Hello, Airflow!")

def print_goodbye():
    print("Goodbye, Airflow!")

def check_service():
    response = requests.get(
        "http://rag-api:8000/api/v1/health",
        timeout=5
    )
    response.raise_for_status()
    print("RAG API is healthy!")

    conn = psycopg2.connect(
        host="postgres",
        database="rag_db",
        user="rag_user",
        password="rag_password",
        port=5432,
        connect_timeout=5,
    )
    conn.close()
    print("All services are healthy!")
    
default_args = {
    "owner": "rag",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="hello_world_dag",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args=default_args,
) as dag:

    check_services_task = PythonOperator(
        task_id="check_services",
        python_callable=check_service,
    )

    hello_task = PythonOperator(
        task_id="print_hello",
        python_callable=print_hello,
    )

    goodbye_task = PythonOperator(
        task_id="print_goodbye",
        python_callable=print_goodbye,
    )

    check_services_task >> hello_task >> goodbye_task