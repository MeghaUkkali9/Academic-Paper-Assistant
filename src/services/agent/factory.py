from typing import Optional

from langgraph.graph.state import CompiledStateGraph

from src.config import Settings, get_settings
from src.services.agent.graph import build_agent_graph
from src.services.agent.nodes import AgentNodes
from src.services.embedding.client import EmbeddingClient
from src.services.openai_llm.client import OpenAILLMClient
from src.services.opensearch.client import OpenSearchClient


def create_rag_agent(
    opensearch_client: OpenSearchClient,
    embedding_client: EmbeddingClient,
    llm_client: OpenAILLMClient,
    settings: Optional[Settings] = None,
) -> CompiledStateGraph:
    """Build the compiled agentic RAG graph."""
    if settings is None:
        settings = get_settings()

    chat_model = llm_client.get_langchain_model(model=settings.openai_model, temperature=0.0)
    nodes = AgentNodes(opensearch_client, embedding_client, llm_client, chat_model)
    return build_agent_graph(nodes, settings.agent)
