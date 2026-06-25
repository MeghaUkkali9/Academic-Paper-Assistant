from typing import List
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
        try:
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
            async with httpx.AsyncClient(timeout = self._settings.timeout_seconds) as client:
                response = await client.post(
                    f"{self._settings.base_url}/embeddings", 
                    headers = headers,
                    json = request_data.model_dump()
                )
                response.raise_for_status()
                    
            result = EmbeddingResponse.model_validate(response.json())
            return result 
        except httpx.HTTPStatusError as httpstatuserror:
            logger.exception(f"Embedding API failed. Status={httpstatuserror.response.status_code} Response={httpstatuserror.response.text}")
            raise
        except Exception:
            logger.exception("Unexpected error while generating embeddings.")
            raise
    
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
            
            batch_embeddings = [
                item.embedding
                for item in result.data
            ]
            
            embeddings.extend(batch_embeddings)
            
        logger.info(f"Successfully embedded {len(texts)} passages")      
        return embeddings 
        
        
    