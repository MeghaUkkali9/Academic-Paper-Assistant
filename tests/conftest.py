import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.config import ChunkingSettings
from src.schemas.indexing.index_paper import PaperForIndexing
from src.services.chunking.chunking import DocumentChunker


@pytest.fixture
def chunking_settings() -> ChunkingSettings:
    return ChunkingSettings(chunk_size=600, overlap_size=100, min_chunk_size=100, section_based=True)


@pytest.fixture
def chunker(chunking_settings: ChunkingSettings) -> DocumentChunker:
    # DocumentChunker only reads settings.chunking.*, so a lightweight
    # namespace avoids needing a full Settings() with real credentials.
    return DocumentChunker(SimpleNamespace(chunking=chunking_settings))


def make_paper(**overrides) -> PaperForIndexing:
    defaults = dict(
        paper_id=uuid.uuid4(),
        arxiv_id="2607.00001v1",
        title="A Test Paper About Testing",
        authors=["Jane Doe", "John Smith"],
        abstract="This paper studies how to test software effectively.",
        categories=["cs.AI"],
        published_on=datetime(2026, 7, 1, tzinfo=timezone.utc),
        raw_text="",
        sections=None,
    )
    defaults.update(overrides)
    return PaperForIndexing(**defaults)


@pytest.fixture
def make_test_paper():
    return make_paper
