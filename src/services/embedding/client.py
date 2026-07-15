from typing import List
import asyncio
import httpx
import logging

from src.config import Settings
from src.schemas.embedding.embedding import EmbeddingRequest, EmbeddingResponse

logger = logging.getLogger(__name__)

class EmbeddingClient:
    
    def __init__(self, settings: Settings):
        self._settings = settings.embedding
        
    async def _embed(
        self,
        texts: List[str],
        task: str
    ) -> EmbeddingResponse:
        headers = {
                "Authorization": f"Bearer {self._settings.jina_api_key}",
                "Content-Type": self._settings.content_type,
            }
        request_data = EmbeddingRequest(
            model=self._settings.embedding_model,
            task=task,
            dimensions=self._settings.dimensions,
            input=texts,
        )

        attempt = 0
        while True:
            try:
                async with httpx.AsyncClient(timeout = self._settings.timeout_seconds) as client:
                    response = await client.post(
                        f"{self._settings.base_url}",
                        headers = headers,
                        json = request_data.model_dump()
                    )
                    response.raise_for_status()

                return EmbeddingResponse.model_validate(response.json())
            except httpx.HTTPStatusError as httpstatuserror:
                status_code = httpstatuserror.response.status_code
                logger.error(f"Embedding API failed. Status={status_code} Response={httpstatuserror.response.text}")

                if status_code == 429 and attempt < self._settings.max_retries_on_rate_limit:
                    wait_seconds = self._get_retry_wait_seconds(httpstatuserror.response, attempt)
                    logger.warning(f"Rate limited by Jina, retrying in {wait_seconds:.0f}s (attempt {attempt + 1}/{self._settings.max_retries_on_rate_limit})")
                    await asyncio.sleep(wait_seconds)
                    attempt += 1
                    continue

                raise
            except Exception:
                logger.exception("Unexpected error while generating embeddings.")
                raise

    def _get_retry_wait_seconds(self, response: httpx.Response, attempt: int) -> float:
        """Wait time for a rate-limited retry: honor Retry-After if present, else back off."""
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return float(retry_after)
            except ValueError:
                pass

        return self._settings.retry_backoff_seconds * (attempt + 1)
    
    async def embed_query(self, query: str) -> List[float]:
        """Embed query"""
          
        result = await self._embed(
            texts=[query], 
            task=self._settings.embedding_query_retrival_task
        )
        embedding = result.data[0].embedding
            
        logger.info(f"Successfully embedded query of length {len(query)}")
        return embedding
    
    async def embed_passages(self, texts: List[str]) -> List[List[float]]:
        """Embed text passages"""
        
        batch_size = self._settings.embedding_batch_size
            
        embeddings = []
            
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            result = await self._embed(
                texts=batch, 
                task=self._settings.embedding_passage_retrival_task
            )
            if len(result.data) != len(batch):
                raise ValueError(
                    f"Batch starting at {i}: expected {len(batch)} embeddings, got {len(result.data)}"
                )
            # Sort by API-provided index to guarantee response order matches input order
            sorted_data = sorted(result.data, key=lambda x: x.index)
            
            batch_embeddings = [
                item.embedding
                for item in sorted_data
            ]
            
            embeddings.extend(batch_embeddings)

            await asyncio.sleep(self._settings.rate_limit_delay_seconds)

        logger.info(f"Successfully embedded {len(texts)} passages")
        return embeddings
        
        
    