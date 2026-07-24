import json
from unittest.mock import AsyncMock

import pytest

from src.config import RedisSettings, Settings
from src.services.cache.client import CacheClient


@pytest.fixture
def client() -> CacheClient:
    settings = Settings.model_construct(
        redis_url="redis://localhost:6379/0",
        redis=RedisSettings(ttl_hours=6),
    )
    cache_client = CacheClient(settings)
    cache_client._redis = AsyncMock()
    return cache_client


class TestBuildKey:
    def test_deterministic_for_equivalent_params(self, client):
        key1 = client.build_key("stream", query="hello", top_k=3, use_hybrid=True, model="gpt-4o-mini", categories=None)
        key2 = client.build_key("stream", query="hello", top_k=3, use_hybrid=True, model="gpt-4o-mini", categories=None)
        assert key1 == key2

    def test_different_namespace_changes_key(self, client):
        key1 = client.build_key("stream", query="hello")
        key2 = client.build_key("agentic", query="hello")
        assert key1 != key2

    def test_different_params_change_key(self, client):
        key1 = client.build_key("stream", query="hello", top_k=3)
        key2 = client.build_key("stream", query="hello", top_k=5)
        assert key1 != key2

    def test_key_is_namespaced(self, client):
        key = client.build_key("stream", query="hello")
        assert key.startswith("rag:stream:")


class TestGet:
    async def test_returns_none_on_miss(self, client):
        client._redis.get.return_value = None
        result = await client.get("some-key")
        assert result is None

    async def test_returns_parsed_value_on_hit(self, client):
        client._redis.get.return_value = json.dumps({"answer": "42"})
        result = await client.get("some-key")
        assert result == {"answer": "42"}

    async def test_returns_none_on_invalid_json(self, client):
        client._redis.get.return_value = "not json"
        result = await client.get("some-key")
        assert result is None

    async def test_returns_none_when_redis_raises(self, client):
        client._redis.get.side_effect = ConnectionError("boom")
        result = await client.get("some-key")
        assert result is None


class TestSet:
    async def test_writes_json_with_ttl(self, client):
        await client.set("some-key", {"answer": "42"})
        client._redis.set.assert_awaited_once_with("some-key", json.dumps({"answer": "42"}), ex=6 * 3600)

    async def test_swallows_redis_errors(self, client):
        client._redis.set.side_effect = ConnectionError("boom")
        await client.set("some-key", {"answer": "42"})  # should not raise


class TestAclose:
    async def test_closes_underlying_connection(self, client):
        await client.aclose()
        client._redis.aclose.assert_awaited_once()
