import asyncio
import logging
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from dateutil import parser

from src.config import Settings, get_settings
from src.exceptions import DownloadParsingException
from src.schemas.arxiv.researchpaper import ArxivResearchPaper
from src.schemas.pdf_parser.models import (
    ArxivMetadata,
    ParsedPaper,
)
from src.services.arxiv.client import ArxivClient
from src.services.pdf_parser.parser import PDFParserService
from src.database.model.paper import PaperCreate
from src.repositories.researchpaper import PaperRepository
from src.exceptions import PaperNotSavedException

logger = logging.getLogger(__name__)

class ResearchPaperManager:
    """
    Orchestrates the research paper pipeline:

    1. Fetch papers from arXiv
    2. Download PDFs
    3. Parse PDFs
    4. Store papers in database
    """

    def __init__(
        self,
        arxiv_client: ArxivClient,
        pdf_parser: PDFParserService,
        settings: Optional[Settings] = None,
    ):
        self.arxiv_client = arxiv_client
        self.pdf_parser = pdf_parser
        self.settings = settings or get_settings()

        self.download_semaphore = asyncio.Semaphore(
            self.settings.arxiv.max_concurrent_downloads
        )

        self.parse_semaphore = asyncio.Semaphore(
            self.settings.arxiv.max_concurrent_parsing
        )

    async def process_papers(
        self,
        db_session: Session,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> dict[str, int]:

        research_papers = await self.arxiv_client.fetch_research_papers(
                from_date=from_date,
                to_date=to_date,
            )
        
        parsed_papers = await self._download_and_parse_papers(
                research_papers
            )
        

        papers_stored = await self._store_papers_to_db(
            parsed_papers,
            db_session,
        )

        return {
            "papers_fetched": len(research_papers),
            "papers_parsed": len(parsed_papers),
            "papers_stored": papers_stored,
        }

    async def _download_and_parse_papers(self, research_papers: list[ArxivResearchPaper]) -> dict[str, ParsedPaper]:
        tasks = [
            self._download_and_parse_task(
                research_paper
            )
            for research_paper in research_papers
        ]

        results = await asyncio.gather(*tasks,return_exceptions=True)

        parsed_papers: dict[str, ParsedPaper] = {}

        for paper, result in zip(research_papers, results):
            if isinstance(result, Exception):
                logger.error(f"Failed processing {paper.arxiv_id}: {result}")
                continue

            if result is not None:
                parsed_papers[paper.arxiv_id] = result

        return parsed_papers

    async def _download_and_parse_task(
        self,
        research_paper: ArxivResearchPaper,
    ) -> Optional[ParsedPaper]:

        try:
            async with self.download_semaphore:
                logger.info(f"Downloading PDF {research_paper.arxiv_id}")
                pdf_path = await self.arxiv_client.download_pdf(research_paper)

            async with self.parse_semaphore:
                logger.info(f"Parsing PDF {research_paper.arxiv_id}")
                pdf_content = await self.pdf_parser.parse_pdf(pdf_path)
                

            metadata = ArxivMetadata(
                arxiv_id=research_paper.arxiv_id,
                title=research_paper.title,
                authors=research_paper.authors,
                categories=research_paper.categories,
                summary=research_paper.summary,
                published_date=research_paper.published_date,
                pdf_url=research_paper.pdf_url
            
            )

            return ParsedPaper(
                arxiv_metadata=metadata,
                pdf_content=pdf_content,
            )

        except Exception as e:
            logger.exception(f"Failed processing paper {research_paper.arxiv_id}")
            raise DownloadParsingException(f"Failed processing paper {research_paper.arxiv_id}") from e

    async def _store_papers_to_db(
        self,
        parsed_papers: dict[str, ParsedPaper],
        db_session: Session,
    ) -> int:

        paper_repository = PaperRepository(
            db_session
        )

        stored_count = 0

        try:
            for parsed_paper in parsed_papers.values():

                paper_create = self._map_to_create_model(parsed_paper)

                paper_repository.upsert(paper_create)

                stored_count += 1

            db_session.commit()

            logger.info(f"Stored {stored_count} papers")

            return stored_count

        except Exception as e:
            db_session.rollback()
            raise PaperNotSavedException(f"Paper not saved {e}") from e
    
    def _map_to_create_model(self, parsed_paper: ParsedPaper) -> PaperCreate:

        metadata = parsed_paper.arxiv_metadata
        pdf_content = parsed_paper.pdf_content
        published_on = (
                    parser.parse(metadata.published_date) if isinstance(metadata.published_date, str) else metadata.published_date
                )
        return PaperCreate(
            arxiv_id=metadata.arxiv_id,
            title=metadata.title,
            authors=metadata.authors,
            summary=metadata.summary,
            categories=metadata.categories,
            published_on=published_on,
            pdf_url=metadata.pdf_url,
            is_indexed = False,
            raw_text=pdf_content.raw_text,
            sections=[
                {
                    "title": section.title,
                    "content": section.content,
                }
                for section in pdf_content.sections
            ],
            parser_used=pdf_content.parser_used,
            parser_metadata=pdf_content.metadata or {},
            pdf_processed=True,
            pdf_processing_date=datetime.now(),
        )