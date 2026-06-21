from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

class ParserType(str, Enum):
    """PDF parser types."""
    DOCLING = "docling"


class PaperSection(BaseModel):
    """Section of a paper."""
    title: str 
    content: str

class PdfContent(BaseModel):
    """PDF specific content"""
    sections: List[PaperSection] 
    raw_text: str
    parser_used: ParserType 
    metadata: Dict[str, Any] 


class ArxivMetadata(BaseModel):
    """Paper metadata from arXiv API."""
    arxiv_id: str
    title: str 
    categories: List[str]
    authors: List[str]
    summary: str 
    published_date: str 
    pdf_url: str 


class ParsedPaper(BaseModel):
    """Complete parsed paper data combining arXiv metadata and PDF content."""
    arxiv_metadata: ArxivMetadata 
    pdf_content: Optional[PdfContent] 