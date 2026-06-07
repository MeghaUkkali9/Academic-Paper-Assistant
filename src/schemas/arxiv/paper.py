class ArxivPaper:
    def __init__(
        self,
        arxiv_id: str,
        title: str,
        authors: list[str],
        abstract: str,
        pdf_url: str,
    ):
        self.arxiv_id = arxiv_id
        self.title = title
        self.authors = authors
        self.abstract = abstract
        self.pdf_url = pdf_url

    def __repr__(self):
        return (
            f"ArxivPaper("
            f"arxiv_id={self.arxiv_id}, "
            f"title={self.title}, "
            f"authors={self.authors}, "
            f"pdf_url={self.pdf_url})"
        )