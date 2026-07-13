from typing import List, Optional

from pydantic import BaseModel, Field

class RAGResponse(BaseModel):
    answer: str
    sources: List[str] = Field(default_factory=list)
    confidence: Optional[str] = None
    citations: Optional[List[str]] = None