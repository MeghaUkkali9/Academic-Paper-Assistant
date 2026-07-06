import logging
from typing import List
from opensearchpy import OpenSearch, helpers
from src.schemas.indexing.index_paper import ChunkWithEmbedding
from src.config import Settings

logger = logging.getLogger(__name__)

class OpenSearchClient:
    def __init__(self, settings: Settings):
        self._settings = settings.opensearch
        self.index_name = f"{settings.opensearch.index_name}-{settings.opensearch.chunk_index_suffix}"
        self.client = OpenSearch(
                hosts=[settings.opensearch.host],
                use_ssl=False,
                verify_certs=False,
                ssl_show_warn=False,
            )
        
    def get_cluster_health(self):
        return self.client.cluster.health()
    
    def delete_chunks(self, arxiv_id: str):
        try:
            response = self.client.delete_by_query(
                index=self.index_name, 
                body={"query": {"term": {"arxiv_id": arxiv_id}}},
                refresh=True
            )
            deleted_res = response.get("deleted", 0)
            logger.info(f"Deleted {deleted_res} chunks for paper {arxiv_id}")
            
            if deleted_res > 0:
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Error deleting chunks: {e}")
            raise
    
    def bulk_index(self, chunks: List[ChunkWithEmbedding]):
        try:
            actions = []
            for chunk in chunks:
                chunk_data = chunk.chunk
                chunk_data["embedding"] = chunk.embedding

                action = {
                    "_index": self.index_name,
                    "_source": chunk_data
                }
                actions.append(action)

            success, errors = helpers.bulk(
                self.client,
                actions,
                refresh=True
            )

            logger.info(f"Bulk indexed {success} chunks, {len(errors)} failed")
            return {
                "success": success,
                "failed": len(errors)
            }

        except Exception as e:
            logger.error(f"Bulk chunk indexing error: {e}")
            raise