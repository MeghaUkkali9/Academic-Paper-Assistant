from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.agent.nodes import (
    AgentNodes,
    ChunkGrading,
    GroundednessCheck,
    QueryRewrite,
    RouteDecision,
)


def make_chat_model(return_value) -> MagicMock:
    """A ChatOpenAI stand-in whose .with_structured_output(Model).ainvoke(...)
    returns a scripted Pydantic instance."""
    chat_model = MagicMock()
    chat_model.with_structured_output.return_value.ainvoke = AsyncMock(return_value=return_value)
    return chat_model


def base_state(**overrides) -> dict:
    state = {
        "query": "What is a transformer?",
        "original_query": "What is a transformer?",
        "top_k": 3,
        "categories": None,
        "model": "gpt-4o-mini",
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
    state.update(overrides)
    return state


class TestRouteQuery:
    async def test_in_scope_query_passes(self):
        chat_model = make_chat_model(RouteDecision(in_scope=True, reason="academic question"))
        nodes = AgentNodes(None, None, None, chat_model)

        result = await nodes.route_query(base_state())

        assert result["in_scope"] is True
        assert result["guardrail_reason"] is None

    async def test_off_topic_query_is_rejected_with_reason(self):
        chat_model = make_chat_model(RouteDecision(in_scope=False, reason="unrelated to research papers"))
        nodes = AgentNodes(None, None, None, chat_model)

        result = await nodes.route_query(base_state(query="what's the weather today?"))

        assert result["in_scope"] is False
        assert result["guardrail_reason"] == "unrelated to research papers"


class TestReject:
    async def test_reject_builds_answer_from_guardrail_reason(self):
        nodes = AgentNodes(None, None, None, None)
        result = await nodes.reject(base_state(guardrail_reason="prompt injection attempt"))
        assert "prompt injection attempt" in result["answer"]


class TestRetrieve:
    async def test_retrieve_calls_search_and_returns_chunks(self):
        opensearch_client = MagicMock()
        opensearch_client.search.return_value = {
            "hits": [
                {"arxiv_id": "2607.00001v1", "chunk_text": "transformers use self-attention"},
                {"arxiv_id": "2607.00002v1", "chunk_text": "attention is all you need"},
            ]
        }
        embedding_client = SimpleNamespace(embed_query=AsyncMock(return_value=[0.1, 0.2]))
        nodes = AgentNodes(opensearch_client, embedding_client, None, None)

        result = await nodes.retrieve(base_state())

        assert len(result["retrieved_chunks"]) == 2
        assert result["search_mode"] == "hybrid"
        opensearch_client.search.assert_called_once()
        assert opensearch_client.search.call_args.kwargs["use_hybrid"] is True


class TestGradeDocuments:
    async def test_empty_retrieved_chunks_short_circuits(self):
        nodes = AgentNodes(None, None, None, MagicMock())
        result = await nodes.grade_documents(base_state(retrieved_chunks=[]))
        assert result["graded_chunks"] == []

    async def test_filters_to_relevant_indices_and_builds_sources(self):
        chunks = [
            {"arxiv_id": "2607.00001v1", "chunk_text": "relevant chunk"},
            {"arxiv_id": "2607.00002v1", "chunk_text": "irrelevant chunk"},
        ]
        chat_model = make_chat_model(ChunkGrading(relevant_indices=[0]))
        nodes = AgentNodes(None, None, None, chat_model)

        result = await nodes.grade_documents(base_state(retrieved_chunks=chunks))

        assert result["graded_chunks"] == [chunks[0]]
        assert result["sources"] == ["https://arxiv.org/pdf/2607.00001.pdf"]

    async def test_out_of_range_indices_are_ignored(self):
        chunks = [{"arxiv_id": "a1", "chunk_text": "x"}]
        chat_model = make_chat_model(ChunkGrading(relevant_indices=[0, 5, -1]))
        nodes = AgentNodes(None, None, None, chat_model)

        result = await nodes.grade_documents(base_state(retrieved_chunks=chunks))

        assert result["graded_chunks"] == [chunks[0]]


class TestRewriteQuery:
    async def test_rewrite_updates_query_and_increments_retry_count(self):
        chat_model = make_chat_model(QueryRewrite(rewritten_query="transformer architecture self-attention"))
        nodes = AgentNodes(None, None, None, chat_model)

        result = await nodes.rewrite_query(base_state(retrieval_retry_count=0))

        assert result["query"] == "transformer architecture self-attention"
        assert result["retrieval_retry_count"] == 1


class TestGenerate:
    async def test_generate_uses_original_query_and_graded_chunks(self):
        llm_client = SimpleNamespace(generate_rag_answer=AsyncMock(return_value={"answer": "Transformers are..."}))
        nodes = AgentNodes(None, None, llm_client, None)
        chunks = [{"arxiv_id": "a1", "chunk_text": "x"}]

        result = await nodes.generate(base_state(query="rewritten query", graded_chunks=chunks))

        assert result["answer"] == "Transformers are..."
        llm_client.generate_rag_answer.assert_awaited_once_with(
            query="What is a transformer?", chunks=chunks, model="gpt-4o-mini"
        )


class TestCheckGroundedness:
    async def test_grounded_answer_does_not_increment_retry(self):
        chat_model = make_chat_model(GroundednessCheck(grounded=True, reason="fully supported"))
        nodes = AgentNodes(None, None, None, chat_model)

        result = await nodes.check_groundedness(base_state(generation_retry_count=0))

        assert result["is_grounded"] is True
        assert result["generation_retry_count"] == 0

    async def test_ungrounded_answer_increments_retry(self):
        chat_model = make_chat_model(GroundednessCheck(grounded=False, reason="unsupported claim"))
        nodes = AgentNodes(None, None, None, chat_model)

        result = await nodes.check_groundedness(base_state(generation_retry_count=0))

        assert result["is_grounded"] is False
        assert result["generation_retry_count"] == 1


class TestEnforceCitations:
    async def test_answer_with_valid_citation_is_unchanged(self):
        nodes = AgentNodes(None, None, None, None)
        chunks = [{"arxiv_id": "2607.00001v1", "chunk_text": "x"}]
        answer = "Transformers use self-attention [arXiv:2607.00001v1]."

        result = await nodes.enforce_citations(base_state(answer=answer, graded_chunks=chunks))

        assert result["answer"] == answer

    async def test_answer_missing_citation_gets_disclaimer(self):
        nodes = AgentNodes(None, None, None, None)
        chunks = [{"arxiv_id": "2607.00001v1", "chunk_text": "x"}]

        result = await nodes.enforce_citations(base_state(answer="Transformers use self-attention.", graded_chunks=chunks))

        assert "could not be verified" in result["answer"]

    async def test_no_graded_chunks_skips_citation_check(self):
        nodes = AgentNodes(None, None, None, None)
        answer = "No relevant information found."

        result = await nodes.enforce_citations(base_state(answer=answer, graded_chunks=[]))

        assert result["answer"] == answer


class TestNoRelevantEvidence:
    async def test_builds_answer_with_attempt_count(self):
        nodes = AgentNodes(None, None, None, None)
        result = await nodes.no_relevant_evidence(base_state(retrieval_retry_count=2))
        assert "3 retrieval attempt" in result["guardrail_reason"]
