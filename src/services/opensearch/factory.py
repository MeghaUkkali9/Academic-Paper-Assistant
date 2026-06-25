from typing import Optional

from src.config import Settings, get_settings
from src.services.opensearch.client import OpenSearchClient

def get_opensearch_client(settings: Optional[Settings] = None):
    """Create Open Search Client"""
    
    if settings is None:
        settings = get_settings()
        
    return OpenSearchClient(settings)