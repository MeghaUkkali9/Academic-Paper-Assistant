import logging 
from typing import List

from src.services.chunking.chunking import DocumentChunker
from src.services.embedding.client import EmbeddingClient
from src.services.opensearch.client import OpenSearchClient
from src.schemas.indexing.index_paper import PaperForIndexing, ChunkWithEmbedding, IndexingResult

logger = logging.getLogger(__name__)

class IndexingService:
    """Coordinates document chunking, embedding generation and indexing into OpenSearch."""
        
    def __init__(
        self, 
        document_chunker: DocumentChunker,
        embed_client: EmbeddingClient, 
        openSearch_client: OpenSearchClient
    ):
        self.document_chunker = document_chunker
        self.embedding_client = embed_client
        self.openSearch_client = openSearch_client
        
    async def index_papers(self, papers: List[PaperForIndexing]) -> IndexingResult:
        """
        Chunk papers, generate embeddings, and bulk index them into OpenSearch.

        Returns:
            IndexingResult: Summary of the indexing operation.
        """
        result = IndexingResult(
            papers_found=len(papers),
            papers_processed=0,
            papers_failed=0,
            chunks_created=0,
            embeddings_generated=0,
            chunks_indexed=0,
            chunks_indexing_failed=0,
        )
        try:
            for paper in papers:
                chunks = self.document_chunker.chunk_paper(paper=paper)
                
                result.chunks_created += len(chunks)
                logger.info(f"Successfully completed chunking process for arxiv_id: {paper.arxiv_id}")
                
                chunk_texts = [chunk.text for chunk in chunks]
                    
                embeddings = await self.embedding_client.embed_passages(chunk_texts)
                result.embeddings_generated += len(embeddings)
                
                if len(embeddings) != len(chunks):
                    logger.error(f"Embedding count {len(embeddings)} does not match chunk count {len(chunks)} for paper {paper.arxiv_id}")
                    raise ValueError(f"Expected {len(chunks)} embeddings but received {len(embeddings)}.")
                
                chunks_with_embeddings = [
                    ChunkWithEmbedding(
                        chunk=chunk,
                        embedding=embedding,
                    )
                    for chunk, embedding in zip(chunks, embeddings)
                ]
                    
                bulk_result = self.openSearch_client.bulk_index(chunks_with_embeddings)
                result.chunks_indexed += bulk_result.success
                result.chunks_indexing_failed += bulk_result.failed
                
                logger.info(f"Indexed {bulk_result.success} chunks for paper {paper.arxiv_id}")
                
                result.papers_processed += 1
            
            logger.info(f"Indexing completed. Papers processed={result.papers_processed}, " 
                        f"Chunks indexed={result.chunks_indexed}, "
                        f"Chunk indexing failures={result.chunks_indexing_failed}")
            return result
        except Exception as e:
            result.papers_failed += 1
            logger.exception("Unexpected error occurred while indexing pappers")
            raise
                
                
                
                
                
    
    