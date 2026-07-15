import logging
from pathlib import Path
import asyncio

from src.exceptions import PDFParsingException, PDFValidationError
from src.schemas.pdf_parser.models import PdfContent

from .docling import DoclingParser

logger = logging.getLogger(__name__)

class PDFParserService:
    """Main PDF parsing service using Docling only."""

    def __init__(
        self,
        max_pages: int,
        max_file_size_mb: int,
        do_ocr: bool = False,
        do_table_structure: bool = True,
        max_concurrent_parses: int = 2,
    ):
        self.docling_parser = DoclingParser(
            max_pages=max_pages,
            max_file_size_mb=max_file_size_mb,
            do_ocr=do_ocr,
            do_table_structure=do_table_structure
        )
        self._semaphore = asyncio.Semaphore(max_concurrent_parses)

    async def parse_pdf(
        self,
        pdf_path: Path
    ) -> PdfContent:

        if not pdf_path.exists():
            raise PDFValidationError(f"PDF file not found: {pdf_path}")

        try:
            async with self._semaphore:
                return await asyncio.to_thread(
                    self.docling_parser.parse_pdf,
                    pdf_path
                )

        except (PDFParsingException, PDFValidationError):
            raise

        except Exception as e:
            logger.exception(f"Docling parsing error for {pdf_path.name}")
            raise PDFParsingException(f"Docling parsing error for {pdf_path.name}: {e}") from e