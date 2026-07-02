import logging
import sys
import os

logging.basicConfig(level=logging.INFO)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from airflow.dags.arxiv_tasks.index_papers import index_research_papers 

if __name__ == "__main__":
    result = index_research_papers() 
    print("\n--- RESULT ---")
    print(result)