from typing import TYPE_CHECKING, Annotated, Generator, Optional
from fastapi import Depends

from src.services.opensearch.client import OpenSearchClient
from src.services.embedding.client import EmbeddingClient
from src.services.llm.client import OpenAILLMClient

if TYPE_CHECKING:
    from fastapi import Depends, Request
    from sqlalchemy.orm import Session
else:
    try:
        from fastapi import Depends, Request
        from sqlalchemy.orm import Session
    except ImportError:
        pass


def get_llm_client(request: Request) -> OpenAILLMClient:
    return request.app.state.llm_client


OpenSearchDependency = Annotated[OpenSearchClient, Depends(lambda request: request.app.state.opensearch_client)]
EmbeddingsDependency = Annotated[EmbeddingClient, Depends(lambda request: request.app.state.embeddings_client)]
LLMDependency = Annotated[OpenAILLMClient, Depends(get_llm_client)]