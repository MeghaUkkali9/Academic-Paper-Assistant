class ParsedPaperSerializer:

    def serialize(self, parsed_paper) -> dict:

        pdf_content = parsed_paper.pdf_content

        return {
            "raw_text": pdf_content.raw_text,
            "sections": [
                {
                    "title": section.title,
                    "content": section.content,
                }
                for section in pdf_content.sections
            ],
            "references": list(
                pdf_content.references
            ),
            "pdf_processed": True,
        }