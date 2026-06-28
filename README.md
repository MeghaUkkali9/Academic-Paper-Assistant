# Academic Paper Assistant

## What problem does this platform solve?

1. Every day, new AI research papers are published. It is difficult for researchers and engineers to keep up with the latest research because there are too many papers to read. No one can review everything manually.

2. If you are trying to learn a concept, traditional keyword search only looks for exact words. Sometimes research papers use different wording for the same concept, so traditional search may miss relevant papers. To solve this, we use embeddings and vector search, which help find papers with similar meaning even when different words are used.

3. Important information is often not available in the title or abstract. Many useful details are explained inside specific sections of the paper, such as methodology, experiments and results. If you only read titles and abstracts, you may miss important insights.

4. Researchers spend a lot of time searching the web, browsing different sources, and filtering through papers to find relevant information. This process can take hours.

5. General AI tools like ChatGPT may not always have access to the latest research papers. Our platform continuously ingests newly published papers, making it easier to discover up-to-date research and information.

## Tech Stack

1. Docker - Runs all services in containers 
2. Airflow - Scheduler - automatically fetches new papers from arXiv daily
3. Upstash - Redis cache — fast key/value store 
4. Jina AI - Embedding model — converts text to vectors
5. Neon Postgres - Cloud database - stores paper metadata
6. FastAPI - Backend API — handles user requests
7. OpenSearch - Search engine — stores and searches papers(BM25 + vector) 
8. OpenSearch Dashboards - Visual UI - browse what is in OpenSearch

## Architechture
ArXiv Papers
↓
ETL Pipeline (Airflow)
↓
PostgreSQL (metadata) + OpenSearch (vectors)

### Retrieval Pipeline :
  Query -> Embedding Model -> BM25 + Dense Vector Search -> Reciprocal Rank Fusion(RRF) -> Reranker(BGE or Cohere or cross encoder) -> Top K results

### Generation Piplene:
  Top K results from retrieval pipline -> Context Window → Prompt → LLM → Response

![System Architecture](/static/retrival_pipeline.png)

## Getting Started
1. pyproject.toml — defined all Python packages this project needs
2. docker-compose.yml — defined all the infrastructure services (OpenSearch, Airflow, etc.) so Docker runs them automatically without installing anything manually

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
### Install All packages
```
uv sync
```
### Run the project

```bash
docker compose up -d
```
That's it. Docker handles everything — no manual installs needed.

## What happens when you run `docker compose up -d`:
1. Docker reads docker-compose.yml
2. Builds our FastAPI app from Dockerfile
3. Downloads OpenSearch + Dashboards images
4. Starts all containers in the right order
   
5. FastAPI app is live at http://localhost:8000
6. OpenSearch at     http://localhost:9200
7. Dashboards at     http://localhost:5601
8. Airflow at        http://localhost:8080


API Docs (Swagger) :  http://localhost:8000/docs 
Health Check: http://localhost:8000/api/v1/health 

## Useful Commands

```bash
# Start everything
docker compose up -d

# Check status of all containers
docker compose ps

# Watch logs
docker compose logs -f api
docker compose logs -f airflow

# Stop everything (data preserved)
docker compose down

# Stop everything and wipe all data
docker compose down -v

# Rebuild after code changes
docker compose up -d --build

# Open terminal inside the running rag-airflow container.
docker exec -it rag-airflow bash

# Check DAGs
airflow dags list
```

### Verify PostgreSQL Connection:

Connect to the PostgreSQL container:

```bash

docker exec -it rag-postgres psql -U rag_user -d rag_db
s
```

Verify the current database and user:

```sql

SELECT current_database(), current_user;

```

### Start Airflow Scheduler Manually

If DAG runs remain in the **Queued** state and do not start executing, verify that the Airflow Scheduler is running.

To start the scheduler manually inside the Airflow container:

```bash

docker exec -it rag-airflow airflow scheduler

```

The scheduler is responsible for:
- Picking up queued DAG runs
- Scheduling tasks
- Executing task instances


### ETL Pipeline:
Here are the 5 steps in order:
① setup_environment
Checks that everything is alive before starting — connects to the database, connects to OpenSearch (the search engine), and creates the search index.

② fetch_daily_papers
Goes to arXiv's website and downloads yesterday's new AI papers. This is where client.py does its work — building the URL, making the HTTP request, parsing the XML response into ArxivPaper objects.

③ index_papers_hybrid
Takes those papers and stores them in two places — a PostgreSQL database and OpenSearch. The "hybrid" part means it indexes them two ways: by keywords and by meaning (vector embeddings), so you can search them later both ways.

④ generate_daily_report
After everything is stored, produces a summary report of what was ingested — how many papers, any errors, stats. Useful for knowing the pipeline ran correctly.

⑤ cleanup_temp_files
Deletes any PDF files older than 30 days from the /tmp folder to keep disk space under control. The only step that runs a shell command rather than Python.

The flow in one line:

Are we ready? → Fetch papers → Store & index them → Report what happened → Clean up.


## To access Arxiv API:
https://info.arxiv.org/help/api/tou.html

