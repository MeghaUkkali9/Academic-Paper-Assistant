class ArxivPaper:
    def __init__(self, title: str, authors: list[str], abstract: str, pdf_url: str):
        self.title = title
        self.authors = authors
        self.abstract = abstract
        self.pdf_url = pdf_url

    def __repr__(self):
        return f"ArxivPaper(title={self.title}, authors={self.authors}, abstract={self.abstract}, pdf_url={self.pdf_url})"