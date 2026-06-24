from typing import Optional

from src.config import Settings, get_settings
from .client import EmbeddingClient

def get_embedding_client(settings: Optional[Settings] = None):
    """Create Embedding client"""
    
    if settings is None:
        settings = get_settings()
        
    return EmbeddingClient(settings)