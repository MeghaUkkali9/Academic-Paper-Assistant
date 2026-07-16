from unittest.mock import AsyncMock, MagicMock

from src.config import AgentSettings
from src.services.agent.graph import build_agent_graph
from src.services.agent.nodes import AgentNodes


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


def make_mocked_nodes(**node_returns) -> MagicMock:
    """A MagicMock standing in for AgentNodes, with each named node method
    set to an AsyncMock returning the given partial-state-update dict(s).
    Pass a list to script a sequence of different return values per call."""
    nodes = MagicMock(spec=AgentNodes)
    for name, value in node_returns.items():
        method = AsyncMock(side_effect=value) if isinstance(value, list) else AsyncMock(return_value=value)
        setattr(nodes, name, method)
    return nodes


class TestHappyPath:
    async def test_reaches_end_with_grounded_answer(self):
        nodes = make_mocked_nodes(
            route_query={"in_scope": True, "guardrail_reason": None},
            retrieve={"retrieved_chunks": [{"arxiv_id": "a1", "chunk_text": "x"}], "search_mode": "hybrid"},
            grade_documents={"graded_chunks": [{"arxiv_id": "a1", "chunk_text": "x"}], "sources": ["https://arxiv.org/pdf/a1.pdf"]},
            generate={"answer": "Transformers use self-attention [arXiv:a1]."},
            check_groundedness={"is_grounded": True, "generation_retry_count": 0},
            enforce_citations={"answer": "Transformers use self-attention [arXiv:a1]."},
        )
        graph = build_agent_graph(nodes, AgentSettings())

        final_state = await graph.ainvoke(base_state())

        assert final_state["answer"] == "Transformers use self-attention [arXiv:a1]."
        assert final_state["is_grounded"] is True
        nodes.rewrite_query.assert_not_called()
        nodes.reject.assert_not_called()
        nodes.no_relevant_evidence.assert_not_called()


class TestOffTopicRejection:
    async def test_short_circuits_before_retrieval(self):
        nodes = make_mocked_nodes(
            route_query={"in_scope": False, "guardrail_reason": "unrelated to research papers"},
            reject={"answer": "I can only answer questions about the academic papers in this system's index."},
        )
        graph = build_agent_graph(nodes, AgentSettings())

        final_state = await graph.ainvoke(base_state(query="what's the weather today?"))

        assert "I can only answer" in final_state["answer"]
        nodes.retrieve.assert_not_called()
        nodes.generate.assert_not_called()


class TestRetryThenSucceed:
    async def test_rewrites_query_once_then_succeeds(self):
        nodes = make_mocked_nodes(
            route_query={"in_scope": True, "guardrail_reason": None},
            retrieve={"retrieved_chunks": [{"arxiv_id": "a1", "chunk_text": "x"}], "search_mode": "hybrid"},
            grade_documents=[
                {"graded_chunks": [], "sources": []},  # first attempt: nothing relevant
                {"graded_chunks": [{"arxiv_id": "a1", "chunk_text": "x"}], "sources": ["https://arxiv.org/pdf/a1.pdf"]},
            ],
            rewrite_query={"query": "transformer self-attention mechanism", "retrieval_retry_count": 1},
            generate={"answer": "Transformers use self-attention [arXiv:a1]."},
            check_groundedness={"is_grounded": True, "generation_retry_count": 0},
            enforce_citations={"answer": "Transformers use self-attention [arXiv:a1]."},
        )
        graph = build_agent_graph(nodes, AgentSettings(max_retrieval_retries=2))

        final_state = await graph.ainvoke(base_state())

        assert final_state["answer"] == "Transformers use self-attention [arXiv:a1]."
        assert nodes.retrieve.await_count == 2
        assert nodes.grade_documents.await_count == 2
        nodes.rewrite_query.assert_awaited_once()
        nodes.no_relevant_evidence.assert_not_called()


class TestRegenerateOnUngroundedAnswer:
    async def test_regenerates_once_then_succeeds(self):
        nodes = make_mocked_nodes(
            route_query={"in_scope": True, "guardrail_reason": None},
            retrieve={"retrieved_chunks": [{"arxiv_id": "a1", "chunk_text": "x"}], "search_mode": "hybrid"},
            grade_documents={"graded_chunks": [{"arxiv_id": "a1", "chunk_text": "x"}], "sources": ["https://arxiv.org/pdf/a1.pdf"]},
            generate=[
                {"answer": "an ungrounded claim"},
                {"answer": "Transformers use self-attention [arXiv:a1]."},
            ],
            check_groundedness=[
                {"is_grounded": False, "generation_retry_count": 1},
                {"is_grounded": True, "generation_retry_count": 1},
            ],
            enforce_citations={"answer": "Transformers use self-attention [arXiv:a1]."},
        )
        graph = build_agent_graph(nodes, AgentSettings(max_generation_retries=1))

        final_state = await graph.ainvoke(base_state())

        assert final_state["answer"] == "Transformers use self-attention [arXiv:a1]."
        assert nodes.generate.await_count == 2
        assert nodes.check_groundedness.await_count == 2


class TestExhaustedRetries:
    async def test_gives_up_after_max_retries_with_no_relevant_chunks(self):
        nodes = make_mocked_nodes(
            route_query={"in_scope": True, "guardrail_reason": None},
            retrieve={"retrieved_chunks": [], "search_mode": "hybrid"},
            grade_documents={"graded_chunks": [], "sources": []},
            rewrite_query=[
                {"query": "q2", "retrieval_retry_count": 1},
                {"query": "q3", "retrieval_retry_count": 2},
            ],
            no_relevant_evidence={
                "answer": "I could not find relevant information in the indexed papers to answer this question.",
                "guardrail_reason": "No relevant chunks found after 3 retrieval attempt(s)",
            },
        )
        graph = build_agent_graph(nodes, AgentSettings(max_retrieval_retries=2))

        final_state = await graph.ainvoke(base_state())

        assert "could not find relevant information" in final_state["answer"]
        nodes.generate.assert_not_called()
        assert nodes.rewrite_query.await_count == 2
