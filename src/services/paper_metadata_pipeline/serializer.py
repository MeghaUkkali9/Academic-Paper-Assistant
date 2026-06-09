# from src.schemas.pdf_parser.models import ParsedPaper
# from typing import Dict, Any
# import logging
# from datetime import datetime

# logger = logging.getLogger(__name__)

# class ParsedPaperSerializer:

#     def serialize_parsed_content(self, parsed_paper: ParsedPaper) -> Dict[str, Any]:
#         """Serialize ParsedPaper content for database storage.

#         :param parsed_paper: ParsedPaper object with PDF content
#         :type parsed_paper: ParsedPaper
#         :returns: Dictionary with serialized content for database storage
#         :rtype: Dict[str, Any]
#         """
#         try:
#             pdf_content = parsed_paper.pdf_content

#             # Serialize sections
#             sections = [
#                 {
#                     "title": section.title, 
#                     "content": section.content
#                 } for section in pdf_content.sections]

#             references = list(pdf_content.references)

#             return {
#                 "raw_text": pdf_content.raw_text,
#                 "sections": sections,
#                 "references": references,
#                 "parser_used": pdf_content.parser_used.value if pdf_content.parser_used else None,
#                 "parser_metadata": pdf_content.metadata or {},
#                 "pdf_processed": True,
#                 "pdf_processing_date": datetime.now(),
#             }
#         except Exception as e:
#             logger.error(f"Failed to serialize parsed content: {e}")
#             return {"pdf_processed": False, "parser_metadata": {"error": str(e)}}