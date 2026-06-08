import asyncio

from src.domain.results import PDFProcessingResult
from src.schemas.pdf_parser.models import (
    ArxivMetadata,
    ParsedPaper,
)

class PDFProcessor:

    def __init__(
        self,
        arxiv_client,
        pdf_parser,
        max_downloads: int = 5,
        max_parsers: int = 3,
    ):
        self.arxiv_client = arxiv_client
        self.pdf_parser = pdf_parser

        self.max_downloads = max_downloads
        self.max_parsers = max_parsers

    async def process(self, papers) -> PDFProcessingResult:

        result = PDFProcessingResult()

        download_semaphore = asyncio.Semaphore(self.max_downloads)

        parse_semaphore = asyncio.Semaphore(self.max_parsers)

        tasks = [
            self._process_single(
                paper,
                download_semaphore,
                parse_semaphore,
            )
            for paper in papers
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for paper, response in zip(papers, responses):
            if isinstance(response, Exception):
                result.errors.append(str(response))
                continue

            downloaded, parsed_paper = response

            if downloaded:
                result.downloaded += 1

            if parsed_paper:
                result.parsed += 1
                result.parsed_papers[
                    paper.arxiv_id
                ] = parsed_paper

        return result

    async def _process_single(self, paper, download_semaphore, parse_semaphore):

        async with download_semaphore:

            pdf_path = (
                await self.arxiv_client.download_pdf(
                    paper
                )
            )

            if not pdf_path:
                return False, None

        async with parse_semaphore:

            pdf_content = (
                await self.pdf_parser.parse_pdf(
                    pdf_path
                )
            )

            if not pdf_content:
                return True, None

            metadata = ArxivMetadata(
                title=paper.title,
                authors=paper.authors,
                abstract=paper.abstract,
                arxiv_id=paper.arxiv_id,
                categories=paper.categories,
                published_date=paper.published_date,
                pdf_url=paper.pdf_url,
            )

            return (
                True,
                ParsedPaper(
                    arxiv_metadata=metadata,
                    pdf_content=pdf_content,
                ),
            )