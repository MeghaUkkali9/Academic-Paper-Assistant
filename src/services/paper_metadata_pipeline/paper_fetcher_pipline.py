from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from src.services.arxiv.client import ArxivClient
from src.config import Settings, get_settings

class ResearchPaperManager:
    def __init__(
        self,
        arxiv_client: ArxivClient,
        settings: Optional[Settings] = None,
    ):
        self.arxiv_client = arxiv_client
        self.settings = settings or get_settings()

    async def fetch_process_store_papers(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        db_session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Fetch research papers from Arxiv API, parse them and store parsed content to PostgreSQL"""
        
        papers = await self.arxiv_client.fetch_research_papers(
            from_date=from_date,
            to_date=to_date,
        )

        pdf_results = await self.download_and_parse_papers(papers)

        stored_results = await self.store_papers_to_db(
            papers,
            pdf_results.get("parsed_papers", {}),
            db_session,
        )

        return {
            "papers_fetched": len(papers),
            "papers_stored": stored_results,
        }