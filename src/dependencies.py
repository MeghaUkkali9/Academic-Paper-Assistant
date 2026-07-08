from typing import TYPE_CHECKING, Annotated, Generator, Optional
from fastapi import Depends

from src.services.opensearch.client import OpenSearchClient
from src.services.embedding.client import EmbeddingClient

if TYPE_CHECKING:
    from fastapi import Depends, Request
    from sqlalchemy.orm import Session
else:
    try:
        from fastapi import Depends, Request
        from sqlalchemy.orm import Session
    except ImportError:
        pass

OpenSearchDependency = Annotated[OpenSearchClient, Depends(lambda request: request.app.state.opensearch_client)]
EmbeddingsDependency = Annotated[EmbeddingClient, Depends(lambda request: request.app.state.embeddings_client)]