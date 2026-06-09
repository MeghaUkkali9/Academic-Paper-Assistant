# import asyncio
# from typing import Any, Dict, List
# from src.exceptions import MetadataFetchingException
# from src.schemas.arxiv.paper import ArxivPaper
# from src.schemas.pdf_parser.models import ArxivMetadata, ParsedPaper
# from src.services.arxiv.client import ArxivClient

# import logging

# logger = logging.getLogger(__name__)

# class PDFProcessor:
#     def __init__(
#         self,
#         arxiv_client: ArxivClient,
#         pdf_parser,
#         max_concurrent_downloads = 5,
#         max_concurrent_parsing: int = 3,
#     ):
#         self.arxiv_client = arxiv_client
#         self.pdf_parser = pdf_parser
#         self.max_concurrent_downloads = max_concurrent_downloads
#         self.max_concurrent_parsing = max_concurrent_parsing

#     async def process_pdfs(self, papers: List[ArxivPaper]) -> Dict[str, Any]:
#         """
#         Process PDFs for a batch of papers with async concurrency.

#         Uses overlapping download+parse pipeline:
#         - Downloads happen concurrently (up to max_concurrent_downloads)
#         - As each download completes, parsing starts immediately
#         - Multiple PDFs can be parsing while others are still downloading

#         This is optimal for production workloads like 100 papers/day.

#         Args:
#             papers: List of ArxivPaper objects

#         Returns:
#             Dictionary with processing results and statistics
#         """
#         results = {
#             "downloaded": 0,
#             "parsed": 0,
#             "parsed_papers": {},
#             "errors": [],
#             "download_failures": [],
#             "parse_failures": [],
#         }

#         logger.info(f"Starting async pipeline for {len(papers)} PDFs...")
#         logger.info(f"Concurrent downloads: {self.max_concurrent_downloads}")
#         logger.info(f"Concurrent parsing: {self.max_concurrent_parsing}")

#         download_semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
#         parse_semaphore = asyncio.Semaphore(self.max_concurrent_parsing)

#         pipeline_tasks = [self._download_and_parse_pipeline(paper, download_semaphore, parse_semaphore) for paper in papers]

#         pipeline_results = await asyncio.gather(*pipeline_tasks, return_exceptions=True)

#         for paper, result in zip(papers, pipeline_results):
#             if isinstance(result, Exception):
#                 error_msg = f"Pipeline error for {paper.arxiv_id}: {str(result)}"
#                 logger.error(error_msg)
#                 results["errors"].append(error_msg)
#             elif result:
#                 if isinstance(result, tuple) and len(result) == 2:
#                     download_success, parsed_paper = result
#                 else:
#                     error_msg = f"Pipeline error for {paper.arxiv_id}: Unexpected result type {type(result).__name__}"
#                     logger.error(error_msg)
#                     results["errors"].append(error_msg)
#                     continue

#                 if download_success:
#                     results["downloaded"] += 1

#                     if parsed_paper:
#                         results["parsed"] += 1
#                         results["parsed_papers"][paper.arxiv_id] = parsed_paper
#                     else:
#                         results["parse_failures"].append(paper.arxiv_id)
#                 else:
#                     results["download_failures"].append(paper.arxiv_id)
#             else:
#                 results["download_failures"].append(paper.arxiv_id)

#         logger.info(f"PDF processing: {results['downloaded']}/{len(papers)} downloaded, {results['parsed']} parsed")

#         if results["download_failures"]:
#             logger.warning(f"Download failures: {len(results['download_failures'])}")

#         if results["parse_failures"]:
#             logger.warning(f"Parse failures: {len(results['parse_failures'])}")

#         if results["download_failures"]:
#             results["errors"].extend([f"Download failed: {arxiv_id}" for arxiv_id in results["download_failures"]])
#         if results["parse_failures"]:
#             results["errors"].extend([f"PDF parse failed: {arxiv_id}" for arxiv_id in results["parse_failures"]])

#         return results

#     async def _download_and_parse_pipeline(
#         self,
#         paper: ArxivPaper,
#         download_semaphore: asyncio.Semaphore, 
#         parse_semaphore: asyncio.Semaphore
#     ) -> tuple:
#         """
#         Complete download+parse pipeline for a single paper with true parallelism.
#         Downloads PDF, then immediately starts parsing while other downloads continue.

#         Returns:
#             Tuple of (download_success: bool, parsed_paper: Optional[ParsedPaper])
#         """
#         download_success = False
#         parsed_paper = None

#         try:
#             async with download_semaphore:
#                 logger.debug(f"Starting download: {paper.arxiv_id}")
#                 pdf_path = await self.arxiv_client.download_pdf(paper, False)

#                 if pdf_path:
#                     download_success = True
#                     logger.debug(f"Download complete: {paper.arxiv_id}")
#                 else:
#                     logger.error(f"Download failed: {paper.arxiv_id}")
#                     return (False, None)

#             async with parse_semaphore:
#                 logger.debug(f"Starting parse: {paper.arxiv_id}")
#                 pdf_content = await self.pdf_parser.parse_pdf(pdf_path)

#                 if pdf_content:
#                     arxiv_metadata = ArxivMetadata(
#                         title=paper.title,
#                         authors=paper.authors,
#                         abstract=paper.abstract,
#                         arxiv_id=paper.arxiv_id,
#                         categories=paper.categories,
#                         published_date=paper.published_date,
#                         pdf_url=paper.pdf_url,
#                     )

#                     parsed_paper = ParsedPaper(arxiv_metadata=arxiv_metadata, pdf_content=pdf_content)
#                     logger.debug(f"Parse complete: {paper.arxiv_id} - {len(pdf_content.raw_text)} chars extracted")
#                 else:
#                     logger.warning(f"PDF parsing failed for {paper.arxiv_id}, continuing with metadata only")

#         except Exception as e:
#             logger.error(f"Pipeline error for {paper.arxiv_id}: {e}")
#             raise MetadataFetchingException(f"Pipeline error for {paper.arxiv_id}: {e}") from e

#         return (download_success, parsed_paper)
