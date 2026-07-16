from unittest.mock import AsyncMock

import httpx
import pytest

from src.config import EmbeddingSettings, Settings
from src.services.embedding.client import EmbeddingClient


def make_response(status_code: int, json_body: dict, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body,
        headers=headers or {},
        request=httpx.Request("POST", "https://api.jina.ai/v1/embeddings"),
    )


def embedding_payload(n: int) -> dict:
    return {
        "object": "list",
        "model": "test",
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
        "data": [{"object": "embedding", "index": i, "embedding": [float(i)]} for i in range(n)],
    }


@pytest.fixture
def client() -> EmbeddingClient:
    settings = Settings.model_construct(
        embedding=EmbeddingSettings(
            jina_api_key="test-key",
            max_retries_on_rate_limit=3,
            retry_backoff_seconds=0.01,  # keep tests fast
            rate_limit_delay_seconds=0.0,
            embedding_batch_size=100,
        )
    )
    return EmbeddingClient(settings)


class TestEmbedSuccess:
    async def test_embed_query_returns_vector(self, client, mocker):
        mocker.patch("httpx.AsyncClient.post", AsyncMock(return_value=make_response(200, embedding_payload(1))))
        result = await client.embed_query("hello")
        assert result == [0.0]

    async def test_embed_passages_returns_all_vectors_in_order(self, client, mocker):
        mocker.patch("httpx.AsyncClient.post", AsyncMock(return_value=make_response(200, embedding_payload(3))))
        result = await client.embed_passages(["a", "b", "c"])
        assert result == [[0.0], [1.0], [2.0]]

    async def test_embed_passages_sorts_out_of_order_response(self, client, mocker):
        payload = {
            "object": "list",
            "model": "t",
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
            "data": [
                {"object": "embedding", "index": 1, "embedding": [1.0]},
                {"object": "embedding", "index": 0, "embedding": [0.0]},
            ],
        }
        mocker.patch("httpx.AsyncClient.post", AsyncMock(return_value=make_response(200, payload)))
        result = await client.embed_passages(["a", "b"])
        assert result == [[0.0], [1.0]]

    async def test_embed_passages_mismatched_batch_count_raises(self, client, mocker):
        mocker.patch("httpx.AsyncClient.post", AsyncMock(return_value=make_response(200, embedding_payload(1))))
        with pytest.raises(ValueError, match="expected 2 embeddings"):
            await client.embed_passages(["a", "b"])


class TestRateLimitRetry:
    async def test_retries_on_429_then_succeeds(self, client, mocker):
        rate_limited = make_response(429, {"detail": "rate limited"})
        success = make_response(200, embedding_payload(1))
        post_mock = AsyncMock(side_effect=[rate_limited, success])
        mocker.patch("httpx.AsyncClient.post", post_mock)

        result = await client.embed_query("hello")

        assert result == [0.0]
        assert post_mock.await_count == 2

    async def test_gives_up_after_max_retries(self, client, mocker):
        rate_limited = make_response(429, {"detail": "rate limited"})
        post_mock = AsyncMock(return_value=rate_limited)
        mocker.patch("httpx.AsyncClient.post", post_mock)

        with pytest.raises(httpx.HTTPStatusError):
            await client.embed_query("hello")

        # initial attempt + max_retries_on_rate_limit(=3) retries = 4 calls
        assert post_mock.await_count == 4

    async def test_non_429_error_does_not_retry(self, client, mocker):
        server_error = make_response(500, {"detail": "server error"})
        post_mock = AsyncMock(return_value=server_error)
        mocker.patch("httpx.AsyncClient.post", post_mock)

        with pytest.raises(httpx.HTTPStatusError):
            await client.embed_query("hello")

        assert post_mock.await_count == 1

    async def test_retry_after_header_is_honored(self, client, mocker):
        rate_limited = make_response(429, {"detail": "rate limited"}, headers={"Retry-After": "0.02"})
        success = make_response(200, embedding_payload(1))
        post_mock = AsyncMock(side_effect=[rate_limited, success])
        mocker.patch("httpx.AsyncClient.post", post_mock)
        sleep_mock = mocker.patch("asyncio.sleep", AsyncMock())

        await client.embed_query("hello")

        sleep_mock.assert_awaited_once_with(0.02)
