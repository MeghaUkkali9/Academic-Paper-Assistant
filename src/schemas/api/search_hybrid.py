from typing import List, Optional
from pydantic import BaseModel, Field

class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    size: int = Field(10, ge=1, le=100)
    from_: int = Field(0, ge=0, alias="from")
    categories: Optional[List[str]] = Field(None)
    latest_papers: bool = Field(False)
    use_hybrid: bool = Field(True)
    min_score: float = Field(0.0, ge=0.0)

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "query": "machine learning",
                "size": 10,
                "categories": ["cs.AI", "cs.LG"],
                "latest_papers": False,
                "use_hybrid": True,
            }
        }