from typing import Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict):
    """State threaded through the agentic RAG graph. Every node returns a
    partial dict that replaces (not merges) the corresponding keys."""

    query: str
    original_query: str
    top_k: int
    categories: Optional[List[str]]
    model: str

    retrieved_chunks: List[Dict[str, Any]]
    graded_chunks: List[Dict[str, Any]]
    sources: List[str]
    search_mode: str

    retrieval_retry_count: int
    generation_retry_count: int

    in_scope: bool
    is_grounded: bool
    answer: str
    guardrail_reason: Optional[str]
