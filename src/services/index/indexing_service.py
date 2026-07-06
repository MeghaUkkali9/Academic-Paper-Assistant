import logging 
from typing import List

from src.services.chunking.chunking import DocumentChunker
from src.services.embedding.client import EmbeddingClient
from src.services.opensearch.client import OpenSearchClient
from src.schemas.indexing.index_paper import PaperForIndexing, ChunkWithEmbedding, IndexingResult
from src.exceptions import EmbeddingGenerationException

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
               
                self.openSearch_client.delete_chunks(paper.arxiv_id)
               
                chunks = self.document_chunker.chunk_paper(paper=paper)
                
                if not chunks:
                    logger.warning("No chunks created for paper %s.", paper.arxiv_id)
                    result.papers_failed += 1
                    continue
                
                result.chunks_created += len(chunks)
                logger.info(f"Successfully completed chunking process for arxiv_id: {paper.arxiv_id}")
                
                chunk_texts = [chunk.text for chunk in chunks]
                    
                embeddings = await self.embedding_client.embed_passages(chunk_texts)
                result.embeddings_generated += len(embeddings)
                
                if len(embeddings) != len(chunks):
                    result.papers_failed += 1
                    logger.error(f"Embedding count {len(embeddings)} does not match chunk count {len(chunks)} for paper {paper.arxiv_id}")
                    raise EmbeddingGenerationException(f"Expected {len(chunks)} embeddings but received {len(embeddings)}.")
                
                chunks_with_embeddings = [
                    ChunkWithEmbedding(
                        chunk={
                            "arxiv_id": chunk.arxiv_id,
                            "paper_id": chunk.paper_id,
                            "chunk_index": chunk.metadata.chunk_index,
                            "chunk_text": chunk.text,
                            "chunk_word_count": chunk.metadata.word_count,
                            "start_char": chunk.metadata.start_char,
                            "end_char": chunk.metadata.end_char,
                            "section_title": chunk.metadata.section_title,
                            "title": paper.title,
                            "authors": ", ".join(paper.authors),
                            "abstract": paper.abstract,
                            "categories": paper.categories,
                            "published_date": paper.published_on,
                        },
                        embedding=embedding,
                    )
                    for chunk, embedding in zip(chunks, embeddings)
                ]
                    
                bulk_result = self.openSearch_client.bulk_index(chunks_with_embeddings)
                result.chunks_indexed += bulk_result["success"]
                result.chunks_indexing_failed += bulk_result["failed"]

                logger.info(f"Indexed {bulk_result['success']} chunks for paper {paper.arxiv_id}")
                
                result.papers_processed += 1
            
            logger.info(f"Indexing completed. Papers processed={result.papers_processed}, " 
                        f"Chunks indexed={result.chunks_indexed}, "
                        f"Chunk indexing failures={result.chunks_indexing_failed}")
            return result
        except Exception as e:
            result.papers_failed += 1
            logger.exception("Unexpected error occurred while indexing pappers")
            raise
                
                
                
                
                
    
    