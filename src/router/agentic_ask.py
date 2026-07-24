import logging

from fastapi import APIRouter, HTTPException

from src.dependencies import AgentDependency, CacheDependency, SettingsDependency
from src.schemas.api.agentic_ask import AgenticAskRequest, AgenticAskResponse
from src.services.agent.state import GraphState
from src.services.tracing.factory import get_langfuse_handler

logger = logging.getLogger(__name__)
agentic_router = APIRouter(tags=["agentic"])


@agentic_router.post("/agentic-ask")
async def ask_question_agentic(
    request: AgenticAskRequest,
    rag_agent: AgentDependency,
    settings: SettingsDependency,
    cache_client: CacheDependency,
) -> AgenticAskResponse:
    """Agentic RAG: query routing, corrective retrieval with retry, groundedness
    checking, and citation enforcement — see src/services/agent/graph.py.
    Grounded, guardrail-free answers are cached in Redis/Upstash for repeat questions."""

    cache_key = cache_client.build_key(
        "agentic",
        query=request.query.strip().lower(),
        top_k=request.top_k,
        use_hybrid=request.use_hybrid,
        model=request.model,
        categories=sorted(request.categories) if request.categories else None,
    )

    cached = await cache_client.get(cache_key)
    if cached:
        logger.info(f"Cache hit for agentic query: '{request.query}'")
        return AgenticAskResponse(**cached, cached=True)

    initial_state: GraphState = {
        "query": request.query,
        "original_query": request.query,
        "top_k": request.top_k,
        "categories": request.categories,
        "model": request.model,
        "use_hybrid": request.use_hybrid,
        "retrieved_chunks": [],
        "graded_chunks": [],
        "sources": [],
        "search_mode": "bm25",
        "retrieval_retry_count": 0,
        "generation_retry_count": 0,
        "in_scope": True,
        "is_grounded": False,
        "answer": "",
        "guardrail_reason": None,
    }

    handler = get_langfuse_handler(settings)
    invoke_config = {
        "recursion_limit": settings.agent.recursion_limit,
        "callbacks": [handler] if handler else [],
    }

    try:
        final_state: GraphState = await rag_agent.ainvoke(initial_state, config=invoke_config)
    except Exception as e:
        logger.exception("Agentic RAG graph failed")
        raise HTTPException(status_code=500, detail=str(e))

    response = AgenticAskResponse(
        query=request.query,
        answer=final_state["answer"],
        sources=final_state["sources"],
        chunks_used=len(final_state["graded_chunks"]),
        search_mode=final_state["search_mode"],
        retrieval_attempts=final_state["retrieval_retry_count"] + 1,
        chunks_graded_relevant=len(final_state["graded_chunks"]),
        grounded=final_state["is_grounded"],
        guardrail_triggered=final_state["guardrail_reason"],
    )

    if response.grounded and not response.guardrail_triggered:
        await cache_client.set(cache_key, response.model_dump(exclude={"cached"}))

    return response
