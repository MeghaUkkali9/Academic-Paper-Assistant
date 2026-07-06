from datetime import datetime
from typing import Any, List, Dict
from uuid import UUID

from pydantic import BaseModel
from src.schemas.chunking.model import DocumentChunk

class PaperForIndexing(BaseModel):
    paper_id: UUID
    arxiv_id: str

    title: str
    authors: List[str]
    abstract: str

    categories: List[str]
    published_on: datetime

    raw_text: str
    sections: List[Dict[str, Any]] | None = None
    
class ChunkWithEmbedding(BaseModel):
    chunk: Dict[str, Any]
    embedding: List[float]
    
class IndexingResult(BaseModel):
    papers_found: int
    papers_processed: int
    papers_failed: int

    chunks_created: int
    embeddings_generated: int

    chunks_indexed: int
    chunks_indexing_failed: int