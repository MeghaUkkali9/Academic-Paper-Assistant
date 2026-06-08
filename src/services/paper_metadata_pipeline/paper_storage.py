from src.repositories.paper import PaperRepository
from src.schemas.arxiv.paper import PaperCreate
from src.services.paper_metadata_pipeline.serializer import ParsedPaperSerializer

class PaperStorageService:

    def __init__(self, serializer:ParsedPaperSerializer):
        self.serializer = serializer

    def save(self, papers, parsed_papers, db_session) -> int:

        repo = PaperRepository(db_session)

        stored_count = 0

        for paper in papers:

            data = {
                "arxiv_id": paper.arxiv_id,
                "title": paper.title,
                "authors": paper.authors,
                "abstract": paper.abstract,
                "categories": paper.categories,
                "published_date": paper.published_date,
                "pdf_url": paper.pdf_url,
            }

            parsed = parsed_papers.get(paper.arxiv_id)

            if parsed:
                data.update(
                    self.serializer.serialize(parsed)
                )

            repo.upsert(PaperCreate(**data))

            stored_count += 1

        db_session.commit()

        return stored_count