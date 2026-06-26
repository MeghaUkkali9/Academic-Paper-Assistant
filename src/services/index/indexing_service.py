from src.services.chunking.chunking import DocumentChunker
from src.services.embedding.client import EmbeddingClient
from src.services.opensearch.client import OpenSearchClient

class IndexingService:
    def __init__(self, embed_client: EmbeddingClient, openSearch_client: OpenSearchClient):
        self.document_chunker = DocumentChunker()
        self.embedding_client = embed_client
        self.openSearch_client = openSearch_client
    
    async def index_papers(self, papers):
        for paper in papers:
            chunks = self.document_chunker.chunk_paper(paper)
            embedding = await self.embedding_client.embed_passages(chunks)
            
            chunks_with_embedings = []
            for chunk, embedding in zip(chunks, embedding):
                chunk_with_embeding = {
                    "chunk_data": chunk,
                    "embedding": embedding
                }
                chunks_with_embedings.append(chunk_with_embeding)
                
            (success, failed) = self.openSearch_client.bulk_index_insert(chunks_with_embedings)
            
            
            
            
            
    
    