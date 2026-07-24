from typing import Optional

from src.config import Settings, get_settings
from .client import CacheClient


def get_cache_client(settings: Optional[Settings] = None) -> CacheClient:
    """Create Redis/Upstash cache client"""

    if settings is None:
        settings = get_settings()

    return CacheClient(settings)
