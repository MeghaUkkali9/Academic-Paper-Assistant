from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import List


class ArxivPaper(BaseModel):
    arxiv_id: str = Field(..., description="arXiv paper ID")
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    published_date: datetime
    pdf_url: HttpUrl