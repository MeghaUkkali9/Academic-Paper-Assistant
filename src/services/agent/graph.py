from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.config import AgentSettings
from src.services.agent.nodes import AgentNodes
from src.services.agent.state import GraphState


def build_agent_graph(nodes: AgentNodes, settings: AgentSettings) -> CompiledStateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("route_query", nodes.route_query)
    graph.add_node("reject", nodes.reject)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("grade_documents", nodes.grade_documents)
    graph.add_node("rewrite_query", nodes.rewrite_query)
    graph.add_node("generate", nodes.generate)
    graph.add_node("check_groundedness", nodes.check_groundedness)
    graph.add_node("enforce_citations", nodes.enforce_citations)
    graph.add_node("no_relevant_evidence", nodes.no_relevant_evidence)

    graph.set_entry_point("route_query")

    graph.add_conditional_edges(
        "route_query",
        lambda state: "retrieve" if state["in_scope"] else "reject",
        {"retrieve": "retrieve", "reject": "reject"},
    )
    graph.add_edge("reject", END)

    graph.add_edge("retrieve", "grade_documents")

    def decide_to_generate(state: GraphState) -> str:
        if state["graded_chunks"]:
            return "generate"
        if state["retrieval_retry_count"] < settings.max_retrieval_retries:
            return "rewrite_query"
        return "no_relevant_evidence"

    graph.add_conditional_edges(
        "grade_documents",
        decide_to_generate,
        {"generate": "generate", "rewrite_query": "rewrite_query", "no_relevant_evidence": "no_relevant_evidence"},
    )

    graph.add_edge("rewrite_query", "retrieve")
    graph.add_edge("no_relevant_evidence", END)

    graph.add_edge("generate", "check_groundedness")

    def decide_after_groundedness(state: GraphState) -> str:
        # check_groundedness already incremented generation_retry_count when
        # ungrounded (the way rewrite_query does for the retrieval loop, just
        # inline instead of in a separate node) — so the "give up" threshold
        # compares with > rather than >=, or max_generation_retries=1 would
        # permit zero actual regenerations instead of one.
        if state["is_grounded"] or state["generation_retry_count"] > settings.max_generation_retries:
            return "enforce_citations"
        return "generate"

    graph.add_conditional_edges(
        "check_groundedness",
        decide_after_groundedness,
        {"enforce_citations": "enforce_citations", "generate": "generate"},
    )

    graph.add_edge("enforce_citations", END)

    return graph.compile()
