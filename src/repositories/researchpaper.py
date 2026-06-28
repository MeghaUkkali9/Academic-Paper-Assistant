from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.database.arxivpaper import ResearchPaper
from src.database.model.paper import PaperCreate

class PaperRepository:
    def __init__(self, session: Session):
        self.session = session
        
    def get_unindexed_papers(self) -> list[ResearchPaper]:
        stmt = select(ResearchPaper).where(
            ResearchPaper.is_indexed == False
        )
        return self.session.scalars(stmt).all()
    
    def mark_papers_as_indexed(self, papers: List[ResearchPaper]) -> None:
        if not papers:
            return

        for paper in papers:
            paper.is_indexed = True

        self.session.commit()
    
    def get_by_arxiv_id(self, arxiv_id: str) -> Optional[ResearchPaper]:
        stmt = select(ResearchPaper).where(ResearchPaper.arxiv_id == arxiv_id)
        return self.session.scalar(stmt)

    def create(self, paper: PaperCreate) -> ResearchPaper:
        db_paper = ResearchPaper(**paper.model_dump())
        self.session.add(db_paper)
        self.session.commit()
        self.session.refresh(db_paper)
        return db_paper
    
    def update(self, paper: ResearchPaper) -> ResearchPaper:
        self.session.add(paper)
        self.session.commit()
        self.session.refresh(paper)
        return paper

    def upsert(self, paper_create: PaperCreate) -> ResearchPaper:
        existing_paper = self.get_by_arxiv_id(paper_create.arxiv_id)
        if existing_paper:
            for key, value in paper_create.model_dump(exclude_unset=True).items():
                setattr(existing_paper, key, value)
            return self.update(existing_paper)
        else:
            return self.create(paper_create)