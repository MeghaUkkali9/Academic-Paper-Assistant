import json
import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.dependencies import CacheDependency, EmbeddingsDependency, LLMDependency, OpenSearchDependency
from src.schemas.api.ask import AskRequest, AskResponse
from src.services.opensearch.utils import build_pdf_sources

logger = logging.getLogger(__name__)
stream_router = APIRouter(tags=["stream"])

async def _prepare_chunks_and_sources(
    request: AskRequest,
    opensearch_client,
    embeddings_service,
):
    """Shared function to prepare chunks and sources for RAG."""
    query_embedding = None
    search_mode = "bm25"

    if request.use_hybrid:
        try:
            query_embedding = await embeddings_service.embed_query(request.query)
            search_mode = "hybrid"
            logger.info("Generated query embedding for hybrid search")
        except Exception as e:
            logger.warning(f"Failed to generate embeddings, falling back to BM25: {e}")
            query_embedding = None
            search_mode = "bm25"

    logger.info(f"Retrieving top {request.top_k} chunks for query: '{request.query}'")

    search_results = opensearch_client.search(
        query=request.query,
        query_embedding=query_embedding,
        size=request.top_k,
        from_=0,
        categories=request.categories,
        use_hybrid=request.use_hybrid and query_embedding is not None,
        min_score=0.0,
    )
    
    chunks = [
        {
            "arxiv_id": hit.get("arxiv_id", ""),
            "chunk_text": hit.get("chunk_text", hit.get("abstract", "")),
        }
        for hit in search_results.get("hits", [])
    ]
    sources = build_pdf_sources(chunks)

    return chunks, sources, search_mode


def _build_cache_key(cache_client, namespace: str, request: AskRequest) -> str:
    return cache_client.build_key(
        namespace,
        query=request.query.strip().lower(),
        top_k=request.top_k,
        use_hybrid=request.use_hybrid,
        model=request.model,
        categories=sorted(request.categories) if request.categories else None,
    )

@stream_router.post("/stream")
async def ask_question_stream(
    request: AskRequest,
    opensearch_client: OpenSearchDependency,
    embeddings_service: EmbeddingsDependency,
    llm_client: LLMDependency,
    cache_client: CacheDependency,
) -> StreamingResponse:
    """Streaming RAG endpoint (no tracing) with a Redis/Upstash cache for repeat questions."""

    cache_key = _build_cache_key(cache_client, "stream", request)

    async def generate_stream():
        start_time = time.time()

        try:
            cached = await cache_client.get(cache_key)
            if cached:
                logger.info(f"Cache hit for query: '{request.query}'")
                metadata_response = {
                    "sources": cached["sources"],
                    "chunks_used": cached["chunks_used"],
                    "search_mode": cached["search_mode"],
                    "cached": True,
                }
                yield f"data: {json.dumps(metadata_response)}\n\n"
                yield f"data: {json.dumps({'chunk': cached['answer']})}\n\n"
                yield f"data: {json.dumps({'answer': cached['answer'], 'done': True})}\n\n"
                return

            chunks, sources, _ = await _prepare_chunks_and_sources(
                request, opensearch_client, embeddings_service
            )

            if not chunks:
                yield f"data: {json.dumps({'answer': 'No relevant information found.', 'sources': [], 'done': True})}\n\n"
                return

            search_mode = "bm25" if not request.use_hybrid else "hybrid"
            metadata_response = {
                "sources": sources,
                "chunks_used": len(chunks),
                "search_mode": search_mode,
                "cached": False,
            }
            yield f"data: {json.dumps(metadata_response)}\n\n"

            from src.services.openai_llm.prompts import RAGPromptBuilder

            prompt_builder = RAGPromptBuilder()
            final_prompt = prompt_builder.create_rag_prompt(request.query, chunks)

            full_response = ""
            async for chunk in llm_client.generate_rag_answer_stream(
                query=request.query,
                chunks=chunks,
                model=request.model
            ):
                if chunk.get("response"):
                    text_chunk = chunk["response"]
                    full_response += text_chunk
                    yield f"data: {json.dumps({'chunk': text_chunk})}\n\n"

                if chunk.get("done", False):
                    yield f"data: {json.dumps({'answer': full_response, 'done': True})}\n\n"
                    break

            if full_response:
                await cache_client.set(cache_key, {
                    "answer": full_response,
                    "sources": sources,
                    "chunks_used": len(chunks),
                    "search_mode": search_mode,
                })

            logger.info(f"Streaming request completed in {time.time() - start_time:.2f}s")

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(), 
        media_type="text/plain", 
        headers={
            "Cache-Control": "no-cache", 
            "Connection": "keep-alive"
        }
    )