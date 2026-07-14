from typing import Annotated

from fastapi import Depends, Request

from src.services.embedding.client import EmbeddingClient
from src.services.openai_llm.client import OpenAILLMClient
from src.services.opensearch.client import OpenSearchClient


def get_llm_client(request: Request) -> OpenAILLMClient:
    return request.app.state.llm_client


def get_opensearch_client(request: Request) -> OpenSearchClient:
    return request.app.state.opensearch_client


def get_embeddings_client(request: Request) -> EmbeddingClient:
    return request.app.state.embeddings_client


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