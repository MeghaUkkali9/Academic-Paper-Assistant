from src.repositories.paper import PaperRepository
from src.schemas.arxiv.paper import PaperCreate
from src.services.paper_metadata_pipeline.serializer import ParsedPaperSerializer
from src.schemas.arxiv.paper import ArxivPaper
from src.schemas.pdf_parser.models import ParsedPaper
from typing import Dict, List
from sqlalchemy.orm import Session
from dateutil import parser as date_parser
from datetime import datetime
import logging


logger = logging.getLogger(__name__)

class PaperStorageService:

    def __init__(self, serializer:ParsedPaperSerializer):
        self.serializer = serializer

    def _store_papers_to_db(
        self,
        papers: List[ArxivPaper],
        parsed_papers: Dict[str, ParsedPaper],
        db_session: Session,
    ) -> int:
        """
        Store papers and parsed content to database with comprehensive content storage.

        Args:
            papers: List of ArxivPaper metadata
            parsed_papers: Dictionary of parsed PDF content by arxiv_id
            db_session: Database session

        Returns:
            Number of papers stored successfully
        """
        paper_repo = PaperRepository(db_session)
        stored_count = 0

        for paper in papers:
            try:
                # Get parsed content if available
                parsed_paper = parsed_papers.get(paper.arxiv_id)

                # Base paper data
                published_date = (
                    date_parser.parse(paper.published_date) if isinstance(paper.published_date, str) else paper.published_date
                )
                paper_data = {
                    "arxiv_id": paper.arxiv_id,
                    "title": paper.title,
                    "authors": paper.authors,
                    "abstract": paper.abstract,
                    "categories": paper.categories,
                    "published_date": published_date,
                    "pdf_url": paper.pdf_url,
                }

                # Add parsed content if available
                if parsed_paper:
                    parsed_content = self._serialize_parsed_content(parsed_paper)
                    paper_data.update(parsed_content)
                    logger.debug(
                        f"Storing paper {paper.arxiv_id} with parsed content ({len(parsed_content.get('raw_text', '')) if parsed_content.get('raw_text') else 0} chars)"
                    )
                else:
                    # No parsed content - just store metadata
                    paper_data.update(
                        {"pdf_processed": False, "parser_metadata": {"note": "PDF processing not available or failed"}}
                    )
                    logger.debug(f"Storing paper {paper.arxiv_id} with metadata only")

                paper_create = PaperCreate(**paper_data)
                stored_paper = paper_repo.upsert(paper_create)

                if stored_paper:
                    stored_count += 1
                    content_info = "with parsed content" if parsed_paper else "metadata only"
                    logger.debug(f"Stored paper {paper.arxiv_id} to database ({content_info})")

            except Exception as e:
                logger.error(f"Failed to store paper {paper.arxiv_id}: {e}")

        # Commit all changes
        try:
            db_session.commit()
            logger.info(f"Committed {stored_count} papers to database with full content storage")
        except Exception as e:
            logger.error(f"Failed to commit papers to database: {e}")
            db_session.rollback()
            stored_count = 0

        return stored_count
    
    def _serialize_parsed_content(self, parsed_paper: ParsedPaper) -> Dict[str, Any]:
        """Serialize ParsedPaper content for database storage.

        :param parsed_paper: ParsedPaper object with PDF content
        :type parsed_paper: ParsedPaper
        :returns: Dictionary with serialized content for database storage
        :rtype: Dict[str, Any]
        """
        try:
            pdf_content = parsed_paper.pdf_content

            # Serialize sections
            sections = [{"title": section.title, "content": section.content} for section in pdf_content.sections]

            # Serialize references
            references = list(pdf_content.references)  #

            return {
                "raw_text": pdf_content.raw_text,
                "sections": sections,
                "references": references,
                "parser_used": pdf_content.parser_used.value if pdf_content.parser_used else None,
                "parser_metadata": pdf_content.metadata or {},
                "pdf_processed": True,
                "pdf_processing_date": datetime.now(),
            }
        except Exception as e:
            logger.error(f"Failed to serialize parsed content: {e}")
            return {"pdf_processed": False, "parser_metadata": {"error": str(e)}}

