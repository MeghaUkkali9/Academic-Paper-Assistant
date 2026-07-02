from src.services.index.factory import create_indexing_service
from src.database.factory import create_database
from src.repositories.researchpaper import PaperRepository
from src.schemas.indexing.index_paper import PaperForIndexing
import asyncio
import logging

logger = logging.getLogger(__name__)

def index_research_papers(**context):
    """Fetch unindexed papers, generate chunks and embeddings,
    store them in OpenSearch, and mark them as indexed."""
    try:
        database = create_database()
        indexing_service = create_indexing_service()
        
        with database.get_session() as session:
            repository = PaperRepository(session)
            papers = repository.get_unindexed_papers()
    
            if not papers:
                logger.info("No unindexed papers found.")
                return {
                    "papers_found": 0,
                    "papers_processed": 0,
                    "papers_failed": 0,
                    "chunks_created": 0,
                    "embeddings_generated": 0,
                    "chunks_indexed": 0,
                    "chunks_indexing_failed": 0,
                }
                
            logger.info(f"{len(papers)} papers waiting to be indexed.")
            
        papers_for_indexing = [
                PaperForIndexing(
                    arxiv_id=p.arxiv_id,
                    title=p.title,
                    raw_text=p.raw_text,
                    sections=p.sections,
                    paper_id = str(p.id),
                    authors = p.authors,
                    categories = p.categories,
                    published_on = p.published_on,
                    abstract = p.summary
                )
                for p in papers 
    ]
        indexing_result =  asyncio.run(indexing_service.index_papers(papers_for_indexing))
        logger.info(f"Indexing completed. Processed={indexing_result.papers_processed} papers,"
                        f"Indexed={indexing_result.chunks_indexed} chunks, "
                        f"Failed={ indexing_result.chunks_indexing_failed} chunks.")
            
        with database.get_session() as session:
            repository = PaperRepository(session)
            repository.mark_papers_as_indexed(papers)
        
        task_instance = context.get("ti")
        
        if task_instance:
            task_instance.xcom_push(
                key="indexing_result",
                value=indexing_result.model_dump(),
            )
            
        return indexing_result.model_dump()
    except Exception as e:
        logger.exception("Failed to index research papers.")
        raise