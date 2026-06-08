from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import List, Optional, Dict, Any


class ArxivPaper(BaseModel):
    arxiv_id: str = Field(..., description="arXiv paper ID")
    title: str
    authors: List[str]
    abstract: str
    categories: List[str]
    published_date: datetime
    pdf_url: HttpUrl
    
class PaperBase(BaseModel):
    arxiv_id: str 
    title: str 
    authors: List[str] 
    abstract: str 
    categories: List[str] 
    published_date: datetime 
    pdf_url: str 

class PaperCreate(PaperBase):
    raw_text: Optional[str] 
    sections: Optional[List[Dict[str, Any]]] 
    references: Optional[List[Dict[str, Any]]] 
    
    parser_used: Optional[str]
    parser_metadata: Optional[Dict[str, Any]]
    pdf_processed: Optional[bool] 
    pdf_processing_date: Optional[datetime] 
