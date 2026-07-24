from typing import Annotated

from fastapi import Depends, Request
from langgraph.graph.state import CompiledStateGraph

from src.config import Settings
from src.services.cache.client import CacheClient
from src.services.embedding.client import EmbeddingClient
from src.services.openai_llm.client import OpenAILLMClient
from src.services.opensearch.client import OpenSearchClient


def get_llm_client(request: Request) -> OpenAILLMClient:
    return request.app.state.llm_client


def get_cache_client(request: Request) -> CacheClient:
    return request.app.state.cache_client


def get_opensearch_client(request: Request) -> OpenSearchClient:
    return request.app.state.opensearch_client


def get_embeddings_client(request: Request) -> EmbeddingClient:
    return request.app.state.embeddings_client


def get_rag_agent(request: Request) -> CompiledStateGraph:
    return request.app.state.rag_agent


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


OpenSearchDependency = Annotated[
    OpenSearchClient,
    Depends(get_opensearch_client),
]

EmbeddingsDependency = Annotated[
    EmbeddingClient,
    Depends(get_embeddings_client),
]

LLMDependency = Annotated[
    OpenAILLMClient,
    Depends(get_llm_client),
]

AgentDependency = Annotated[
    CompiledStateGraph,
    Depends(get_rag_agent),
]

SettingsDependency = Annotated[
    Settings,
    Depends(get_app_settings),
]

CacheDependency = Annotated[
    CacheClient,
    Depends(get_cache_client),
]