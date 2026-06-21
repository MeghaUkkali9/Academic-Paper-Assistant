from pydantic import BaseModel
from typing import List

class ArxivResearchPaper(BaseModel):
    arxiv_id: str 
    title: str
    authors: List[str]
    summary: str
    categories: List[str]
    published_date: str
    pdf_url: str
    