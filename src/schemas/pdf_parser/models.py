from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

class ParserType(str, Enum):
    """PDF parser types."""
    DOCLING = "docling"


class PaperSection(BaseModel):
    """Represents a section of a paper."""
    title: str 
    content: str 
    level: int 


class PaperFigure(BaseModel):
    """Represents a figure in a paper."""
    caption: str
    id: str


class PaperTable(BaseModel):
    """Represents a table in a paper."""
    caption: str 
    id: str


class PdfContent(BaseModel):
    """PDF-specific content extracted by parsers like Docling."""
    sections: List[PaperSection] 
    raw_text: str
    parser_used: ParserType 
    metadata: Dict[str, Any] 


class ArxivMetadata(BaseModel):
    """Paper metadata from arXiv API."""
    title: str 
    authors: List[str]
    abstract: str 
    arxiv_id: str
    categories: List[str]
    published_date: str 
    pdf_url: str 


class ParsedPaper(BaseModel):
    """Complete paper data combining arXiv metadata and PDF content."""
    arxiv_metadata: ArxivMetadata 
    pdf_content: Optional[PdfContent] 