# from src.domain.results import PipelineResult

# class PaperPipeline:
#     def __init__(self, fetch_service, pdf_processor, storage_service):
#         self.fetch_service = fetch_service
#         self.pdf_processor = PDFProcessor(
#                                 arxiv_client=arxiv_client,
#     pdf_parser=pdf_parser,
# )
#         self.storage_service = storage_service

#     async def run(
#         self,
#         db_session,
#         max_results=None,
#         from_date=None,
#         to_date=None,
#     ):

#         papers = (
#             await self.fetch_service.fetch(
#                 max_results=max_results,
#                 from_date=from_date,
#                 to_date=to_date,
#             )
#         )

#         pdf_result = await self.pdf_processor.process(papers)

#         stored_count = (
#             self.storage_service.save(
#                 papers,
#                 pdf_result.parsed_papers,
#                 db_session,
#             )
#         )

#         return PipelineResult(
#             papers_fetched=len(papers),
#             pdfs_downloaded=pdf_result.downloaded,
#             pdfs_parsed=pdf_result.parsed,
#             papers_stored=stored_count,
#             errors=pdf_result.errors,
#         )