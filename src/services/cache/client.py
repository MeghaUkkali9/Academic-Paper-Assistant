import hashlib
import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

from src.config import Settings

logger = logging.getLogger(__name__)


class CacheClient:
    """Caches RAG answers in Redis/Upstash, keyed by the normalized request.

    Read/write failures are logged and swallowed rather than raised, so a
    cache outage degrades to "always miss" instead of breaking the RAG endpoints.
    """

    def __init__(self, settings: Settings):
        self._redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        self._ttl_seconds = settings.redis.ttl_hours * 3600

    @staticmethod
    def build_key(namespace: str, **params: Any) -> str:
        canonical = json.dumps(params, sort_keys=True, default=str)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return f"rag:{namespace}:{digest}"

    async def get(self, key: str) -> Optional[dict]:
        try:
            raw = await self._redis.get(key)
        except Exception as e:
            logger.warning(f"Cache read failed for {key}: {e}")
            return None

        if raw is None:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Cache value for {key} was not valid JSON, ignoring")
            return None

    async def set(self, key: str, value: dict) -> None:
        try:
            await self._redis.set(key, json.dumps(value), ex=self._ttl_seconds)
        except Exception as e:
            logger.warning(f"Cache write failed for {key}: {e}")

    async def aclose(self) -> None:
        await self._redis.aclose()
