import logging
import sys
import os

logging.basicConfig(level=logging.INFO)

# make sure src/ resolves — adjust if your layout differs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from airflow.dags.arxiv_tasks.index_papers import index_research_papers  # adjust import path to match your file

if __name__ == "__main__":
    result = index_research_papers()  # no context -> ti will be None, xcom_push skipped
    print("\n--- RESULT ---")
    print(result)