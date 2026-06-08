from dataclasses import dataclass, field
from typing import Dict

from src.schemas.pdf_parser.models import ParsedPaper

@dataclass
class PDFProcessingResult:
    downloaded: int = 0
    parsed: int = 0
    parsed_papers: Dict[str, ParsedPaper]
    errors: list[str] 

@dataclass
class PipelineResult:
    papers_fetched: int = 0
    pdfs_downloaded: int = 0
    pdfs_parsed: int = 0
    papers_stored: int = 0
    errors: list[str] 