import logging
from typing import List, Dict, Any, Optional
from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import NotFoundError
from src.schemas.indexing.index_paper import ChunkWithEmbedding
from src.config import Settings
from src.services.opensearch.query import QueryBuilder

logger = logging.getLogger(__name__)

HYBRID_RECIPROCALRANKFUSION_PIPELINE = {
    "id": "hybrid-rrf-pipeline",
    "description": "Post processor for hybrid RRF search",
    "phase_results_processors": [
        {
            "score-ranker-processor": {
                "combination": {
                    "technique": "rrf",  
                    "rank_constant": 60, 
                }
            }
        }
    ],
}

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

    def setup_indices(self, force: bool = False) -> Dict[str, bool]:
        """Create the hybrid search index and RRF pipeline if they don't already exist."""
        return {
            "hybrid_index": self._create_hybrid_index(force),
            "rrf_pipeline": self._create_rrf_pipeline(force),
        }

    def _create_hybrid_index(self, force: bool = False) -> bool:
        """Create the hybrid chunk index. Returns True if it was (re)created."""
        try:
            if force and self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
                logger.info(f"Deleted existing hybrid index: {self.index_name}")

            if not self.client.indices.exists(index=self.index_name):
                self.client.indices.create(index=self.index_name, body=self._build_index_mapping())
                logger.info(f"Created hybrid index: {self.index_name}")
                return True

            logger.info(f"Hybrid index already exists: {self.index_name}")
            return False
        except Exception as e:
            # Handle race condition when multiple workers start simultaneously:
            # all check exists() -> False, all try to create, only one succeeds.
            if "resource_already_exists_exception" in str(e):
                logger.info(f"Hybrid index already exists (created by another worker): {self.index_name}")
                return False
            logger.error(f"Error creating hybrid index: {e}")
            raise

    def _create_rrf_pipeline(self, force: bool = False) -> bool:
        """Create the RRF search pipeline. Returns True if it was (re)created."""
        pipeline_id = HYBRID_RECIPROCALRANKFUSION_PIPELINE["id"]
        try:
            pipeline_exists = True
            try:
                self.client.search_pipeline.get(id=pipeline_id)
            except NotFoundError:
                pipeline_exists = False

            if force or not pipeline_exists:
                pipeline_body = {k: v for k, v in HYBRID_RECIPROCALRANKFUSION_PIPELINE.items() if k != "id"}
                self.client.search_pipeline.put(id=pipeline_id, body=pipeline_body)
                logger.info(f"Created RRF search pipeline: {pipeline_id}")
                return True

            logger.info(f"RRF pipeline already exists: {pipeline_id}")
            return False
        except Exception as e:
            logger.error(f"Error creating RRF pipeline: {e}")
            raise

    def _build_index_mapping(self) -> Dict[str, Any]:
        """Index settings and mapping for the hybrid chunk index."""
        return {
            "settings": {
                "index": {
                    "knn": True,
                }
            },
            "mappings": {
                "dynamic": "strict",
                "properties": {
                    "arxiv_id": {"type": "keyword"},
                    "paper_id": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "chunk_text": {"type": "text"},
                    "chunk_word_count": {"type": "integer"},
                    "start_char": {"type": "integer"},
                    "end_char": {"type": "integer"},
                    "section_title": {"type": "keyword"},
                    "title": {"type": "text"},
                    "authors": {"type": "text"},
                    "abstract": {"type": "text"},
                    "categories": {"type": "keyword"},
                    "published_date": {"type": "date"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": self._settings.vector_dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": self._settings.vector_space_type,
                            "engine": "lucene",
                        },
                    },
                },
            },
        }

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
        
    def search(
        self,
        query: str,
        query_embedding: Optional[List[float]] = None,
        size: int = 10,
        from_: int = 0,
        categories: Optional[List[str]] = None,
        latest: bool = False,
        use_hybrid: bool = True,
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Unified search method supporting BM25, vector, and hybrid modes."""
        try:
            if not query_embedding or not use_hybrid:
                return self._search_bm25_only(
                    query=query,
                    size=size, 
                    from_=from_, 
                    categories=categories, 
                    latest=latest)

            return self._search_hybrid(
                query=query, 
                query_embedding=query_embedding, 
                size=size, 
                categories=categories, 
                min_score=min_score
            )

        except Exception:
            logger.exception("Search operation failed")
            return {"total": 0, "hits": []}

    def _search_bm25_only(
        self, query: str, size: int, from_: int, categories: Optional[List[str]], latest: bool
    ) -> Dict[str, Any]:
        """Pure BM25 search implementation."""
        builder = QueryBuilder(
            query=query,
            size=size,
            from_=from_,
            categories=categories,
            latest_papers=latest,
            search_chunks=True,
        )
        search_body = builder.build()

        response = self.client.search(index=self.index_name, body=search_body)

        results = {"total": response["hits"]["total"]["value"], "hits": []}

        for hit in response["hits"]["hits"]:
            chunk = hit["_source"]
            chunk["score"] = hit["_score"]
            chunk["chunk_id"] = hit["_id"]

            if "highlight" in hit:
                chunk["highlights"] = hit["highlight"]

            results["hits"].append(chunk)

        logger.info(f"BM25 search for '{query[:50]}...' returned {results['total']} results")
        return results

    def _search_hybrid(
        self, 
        query: str, 
        query_embedding: List[float], 
        size: int, 
        categories: Optional[List[str]], 
        min_score: float
    ) -> Dict[str, Any]:
        """Native OpenSearch hybrid search with RRF pipeline."""
        
        builder = QueryBuilder(
            query=query,
            size=size * 2, 
            from_=0, 
            categories=categories, 
            latest_papers=False,
            search_chunks=True
        )
        bm25_search_body = builder.build()

        bm25_query = bm25_search_body["query"]

        hybrid_query = {
            "hybrid": 
                {
                    "queries": [bm25_query, {"knn": {"embedding": {"vector": query_embedding, "k": size * 2}}}]
                }
            }

        search_body = {
            "size": size,
            "query": hybrid_query,
            "_source": bm25_search_body["_source"],
            "highlight": bm25_search_body["highlight"],
        }

        response = self.client.search(
            index=self.index_name,
            body=search_body, 
            params={"search_pipeline": HYBRID_RECIPROCALRANKFUSION_PIPELINE["id"]}
        )

        results = {"total": response["hits"]["total"]["value"], "hits": []}

        for hit in response["hits"]["hits"]:
            if hit["_score"] < min_score:
                continue

            chunk = hit["_source"]
            chunk["score"] = hit["_score"]
            chunk["chunk_id"] = hit["_id"]

            if "highlight" in hit:
                chunk["highlights"] = hit["highlight"]

            results["hits"].append(chunk)

        results["total"] = len(results["hits"])
        
        logger.info(f"Native hybrid search for '{query[:50]}...' returned {results['total']} results")
        return results
