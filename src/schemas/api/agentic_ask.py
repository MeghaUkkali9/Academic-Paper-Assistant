from typing import List, Optional

from pydantic import BaseModel, Field


class AgenticAskRequest(BaseModel):
    """Request model for agentic RAG question answering."""

    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(3, ge=1, le=10)
    use_hybrid: bool = Field(True)
    model: str = Field("gpt-4o-mini")
    categories: Optional[List[str]] = Field(None)

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "top_k": 3,
                "use_hybrid": True,
                "model": "gpt-4o-mini",
                "categories": ["cs.AI", "cs.LG"],
            }
        }


class AgenticAskResponse(BaseModel):
    """Response model for agentic RAG question answering."""

    query: str = Field(...)
    answer: str = Field(...)
    sources: List[str] = Field(...)
    chunks_used: int = Field(...)
    search_mode: str = Field(...)

    retrieval_attempts: int = Field(..., description="Number of retrieval attempts, including the first")
    chunks_graded_relevant: int = Field(..., description="Chunks the grading step judged relevant")
    grounded: bool = Field(..., description="Whether the answer passed the groundedness check")
    guardrail_triggered: Optional[str] = Field(None, description="Reason a guardrail fired, if any")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "What are transformers in machine learning?",
                "answer": "Transformers are a neural network architecture... [arXiv:1706.03762]",
                "sources": ["https://arxiv.org/pdf/1706.03762.pdf"],
                "chunks_used": 3,
                "search_mode": "hybrid",
                "retrieval_attempts": 1,
                "chunks_graded_relevant": 3,
                "grounded": True,
                "guardrail_triggered": None,
            }
        }
