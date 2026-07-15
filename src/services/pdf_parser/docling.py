import logging
import os
from pathlib import Path
from typing import Optional
import gc
import pypdfium2 as pdfium
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    AcceleratorOptions,
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

from src.exceptions import PDFParsingException, PDFValidationError
from src.schemas.pdf_parser.models import (
    PaperSection,
    ParserType,
    PdfContent,
)

logger = logging.getLogger(__name__)

class DoclingParser:
    """Docling PDF parser for processing documents."""

    def __init__(
        self,
        max_pages: int,
        max_file_size_mb: int,
        do_ocr: bool = False,
        do_table_structure: bool = False,
    ):
        artifacts_path = os.environ.get(
            "DOCLING_ARTIFACTS_PATH", "/app/.docling-models"
        )
        if not os.path.isdir(artifacts_path):
            # Falls back to Docling's default download-and-cache behavior
            # (e.g. local dev outside the container image).
            artifacts_path = None

        pipeline_options = PdfPipelineOptions(
            do_table_structure=do_table_structure,
            do_ocr=do_ocr,
            artifacts_path=artifacts_path,
            enable_remote_services=False,
            accelerator_options=AcceleratorOptions(
                num_threads=4, device=AcceleratorDevice.CPU
            ),
        )

        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options
                )
            }
        )

        self.max_pages = max_pages
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

        self._warm_up()

    def _warm_up(self) -> None:
        """Force model weights to load at construction time instead of on the first request."""
        blank_pdf = Path(__file__).parent / "_warmup.pdf"
        try:
            self._converter.convert(str(blank_pdf))
            logger.info("Docling models warmed up successfully.")
        except Exception:
            logger.exception("Docling warm-up conversion failed; continuing anyway.")

    def _validate_pdf(self, pdf_path: Path) -> None:
        if not pdf_path.exists():
            raise PDFValidationError(f"PDF does not exist: {pdf_path}")

        file_size = pdf_path.stat().st_size

        if file_size == 0:
            raise PDFValidationError(f"PDF is empty: {pdf_path}")

        if file_size > self.max_file_size_bytes:
            raise PDFValidationError(
                f"PDF too large: "
                f"{file_size / 1024 / 1024:.1f}MB"
            )

        pdf_doc = None

        try:
            pdf_doc = pdfium.PdfDocument(str(pdf_path))
            page_count = len(pdf_doc)

            if page_count > self.max_pages:
                raise PDFValidationError(
                    f"PDF has too many pages: "
                    f"{page_count}"
                )

        finally:
            if pdf_doc:
                pdf_doc.close()

    def parse_pdf(
        self,
        pdf_path: Path
    ) -> PdfContent:
        result = None
        try:
            self._validate_pdf(pdf_path)

            result = self._converter.convert(
                str(pdf_path),
                max_num_pages=self.max_pages,
                max_file_size=self.max_file_size_bytes,
            )

            document = result.document

            sections = []
            current_title = "Content"
            current_content = []

            for element in document.texts:

                if (
                    hasattr(element, "label")
                    and element.label in {
                        "title",
                        "section_header",
                    }
                ):
                    if current_content:
                        sections.append(
                            PaperSection(
                                title=current_title,
                                content="\n".join(
                                    current_content
                                ).strip(),
                            )
                        )

                    current_title = element.text.strip()
                    current_content = []

                elif getattr(element, "text", None):
                    current_content.append(
                        element.text
                    )

            if current_content:
                sections.append(
                    PaperSection(
                        title=current_title,
                        content="\n".join(
                            current_content
                        ).strip(),
                    )
                )

            return PdfContent(
                sections=sections,
                raw_text=document.export_to_text(),
                parser_used=ParserType.DOCLING,
                metadata={
                    "source": "docling",
                },
            )

        except PDFValidationError:
            raise

        except Exception as e:
            logger.exception("Failed to parse PDF with Docling")
            raise PDFParsingException(f"Failed to parse PDF with Docling: {e}") from e
        
        finally:
            result = None
            gc.collect()