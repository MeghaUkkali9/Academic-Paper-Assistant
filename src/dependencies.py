from typing import TYPE_CHECKING, Annotated, Generator, Optional
from fastapi import Depends
from src.services.opensearch.client import OpenSearchClient


if TYPE_CHECKING:
    from fastapi import Depends, Request
    from sqlalchemy.orm import Session
else:
    try:
        from fastapi import Depends, Request
        from sqlalchemy.orm import Session
    except ImportError:
        pass
    
def get_opensearch_client(request: Request) -> OpenSearchClient:
    """Get OpenSearch client from the request state."""
    return request.app.state.opensearch_client

OpenSearchDep = Annotated[OpenSearchClient, Depends(get_opensearch_client)]