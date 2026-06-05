from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

def print_hello():
    print("Hello, Airflow!")

def print_goodbye():
    print("print goodbye")
    
with DAG(
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    dag_id="hello_world_dag"
) as dag:
    
    hello_task = PythonOperator(
        task_id = "print_hello",
        python_callable=print_hello
    )
    
    goodbye_task = PythonOperator(
        task_id = "print_goodbye",
        python_callable = print_goodbye
    )
    
# Define order
hello_task >> goodbye_task