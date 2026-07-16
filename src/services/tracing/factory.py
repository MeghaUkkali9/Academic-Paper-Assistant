import logging
from typing import Optional

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


def init_langfuse(settings: Optional[Settings] = None) -> Optional[Langfuse]:
    """Initialize the global Langfuse client. Call once, at app startup.

    CallbackHandler() binds to whichever Langfuse client was last constructed,
    so this must run before get_langfuse_handler() is ever called.
    """
    if settings is None:
        settings = get_settings()

    if not settings.langfuse.enabled:
        logger.info("Langfuse tracing disabled (LANGFUSE__ENABLED=false)")
        return None

    client = Langfuse(
        public_key=settings.langfuse.public_key,
        secret_key=settings.langfuse.secret_key,
        base_url=settings.langfuse.base_url,
    )
    logger.info("Langfuse tracing initialized")
    return client


def get_langfuse_handler(settings: Optional[Settings] = None) -> Optional[CallbackHandler]:
    """Callback handler for a single graph invocation. None if tracing is disabled."""
    if settings is None:
        settings = get_settings()

    if not settings.langfuse.enabled:
        return None

    return CallbackHandler()
