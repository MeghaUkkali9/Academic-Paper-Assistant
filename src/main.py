from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
import logging
from src.router.ask import stream_router
from src.router.hybrid_search import router as hybrid_search_router
from src.router.user import user_router

from src.database.factory import create_database
from src.services.embedding.factory import get_embedding_client
from src.services.openai_llm.factory import make_openai_llm_client
from src.services.opensearch.factory import get_opensearch_client
from src.services.arxiv.factory import make_arxiv_client
from src.services.pdf_parser.factory import make_pdf_parser_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize application services."""
    logger.info("=== Lifespan started ===")
    
    database = create_database()
    app.state.database = database
    logger.info("Database connected successfully.")

    app.state.arxiv_client = make_arxiv_client()
    app.state.pdf_parser = make_pdf_parser_service()
    app.state.llm_client = make_openai_llm_client()
    app.state.embeddings_client = get_embedding_client()
    app.state.opensearch_client = get_opensearch_client()

    logger.info("=== All services initialized ===")
    
    yield

    # Cleanup resources on shutdown
    database.dispose()
    logger.info("=== API shutdown complete ===")


app = FastAPI(
    title="Academic Paper Assistant API",
    version="1.0",
    lifespan=lifespan,
)

@app.get("/api/v1/health")
def health():
    return {"status": "ok"}

app.include_router(user_router)
app.include_router(hybrid_search_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run(app, port=8000, host="0.0.0.0")
