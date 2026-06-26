from src.services.chunking.chunking import DocumentChunker
from src.services.embedding.factory import get_embedding_client
from src.services.opensearch.factory import get_opensearch_client
from .indexing_service import IndexingService

from typing import Optional
from src.config import Settings, get_settings

def get_indexing_service(settings: Optional[Settings] = None):
    if settings is None:
        settings = get_settings()
    
    document_chunker = DocumentChunker(settings=settings)
    embedding_client = get_embedding_client(settings=settings)
    opensearch_client = get_opensearch_client(settings=settings)
    
    return IndexingService(
        document_chunker=document_chunker,
        embed_client=embedding_client,
        openSearch_client=opensearch_client
    )