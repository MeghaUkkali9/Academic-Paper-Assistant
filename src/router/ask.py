import json
import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from src.dependencies import EmbeddingsDependency, LLMDependency, OpenSearchDependency
from src.schemas.api.ask import AskRequest, AskResponse

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

    # Retrieve top-k chunks
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

    # Extract chunks with minimal data for LLM
    chunks = []
    sources_set = set()  # Use set to automatically handle duplicates

    for hit in search_results.get("hits", []):
        arxiv_id = hit.get("arxiv_id", "")

        # Build minimal chunk for LLM (only content + arxiv_id)
        chunk_data = {
            "arxiv_id": arxiv_id,
            "chunk_text": hit.get("chunk_text", hit.get("abstract", "")),
        }
        chunks.append(chunk_data)

        # Build PDF URL from arxiv_id for sources (automatically deduplicates)
        if arxiv_id:
            arxiv_id_clean = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id_clean}.pdf"
            sources_set.add(pdf_url)

    # Convert set back to list for consistent return type
    sources = list(sources_set)

    return chunks, sources, search_mode

@stream_router.post("/stream")
async def ask_question_stream(
    request: AskRequest,
    opensearch_client: OpenSearchDependency,
    embeddings_service: EmbeddingsDependency,
    llm_client: LLMDependency
) -> StreamingResponse:
    """Clean streaming RAG endpoint (no cache, no tracing)."""

    async def generate_stream():
        start_time = time.time()

        try:
            # Retrieve chunks
            chunks, sources, _ = await _prepare_chunks_and_sources(
                request, opensearch_client, embeddings_service
            )

            if not chunks:
                yield f"data: {json.dumps({'answer': 'No relevant information found.', 'sources': [], 'done': True})}\n\n"
                return

            # Send metadata first
            search_mode = "bm25" if not request.use_hybrid else "hybrid"
            metadata_response = {"sources": sources, "chunks_used": len(chunks), "search_mode": search_mode}
            yield f"data: {json.dumps(metadata_response)}\n\n"

            # Build prompt
            from src.services.llm.prompts import RAGPromptBuilder

            prompt_builder = RAGPromptBuilder()
            final_prompt = prompt_builder.create_rag_prompt(request.query, chunks)

            # Stream generation
            full_response = ""
            async for chunk in llm_client.generate_rag_answer_stream(
                query=request.query, chunks=chunks, model=request.model
            ):
                if chunk.get("response"):
                    text_chunk = chunk["response"]
                    full_response += text_chunk
                    yield f"data: {json.dumps({'chunk': text_chunk})}\n\n"

                if chunk.get("done", False):
                    yield f"data: {json.dumps({'answer': full_response, 'done': True})}\n\n"
                    break

            logger.info(f"Streaming request completed in {time.time() - start_time:.2f}s")

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        generate_stream(), media_type="text/plain", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )