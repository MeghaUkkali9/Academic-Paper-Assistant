from src.services.arxiv.client import ArxivClient
from typing import Optional

class PaperFetchService:
    
    def __init__(self, arxiv_client: ArxivClient):
        self.arxiv_client = arxiv_client
        
    async def fetch(
        self,
        max_results: Optional[int] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ):
        papers = await self.arxiv_client.fetch_papers(
                max_results=max_results, 
                from_date=from_date, 
                to_date=to_date, 
                sort_by="submittedDate", 
                sort_order="descending"
            )
        return papers