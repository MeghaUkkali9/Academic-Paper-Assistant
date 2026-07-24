from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE_PATH = PROJECT_ROOT / ".env"

class BaseConfigSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        extra="ignore",
        frozen=True,
        env_nested_delimiter="__",
        case_sensitive=False,
    )

class ArxivSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="ARXIV__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    base_url: str = "https://export.arxiv.org/api/query"
    pdf_cache_dir: str = "./data/arxiv_pdfs"
    sort_by: Literal[
        "relevance",
        "lastUpdatedDate",
        "submittedDate"
    ] = "submittedDate"
    sort_order: Literal[
        "ascending",
        "descending"
    ] = "descending"
    rate_limit_delay: float = 3.0
    timeout_seconds: int = 60
    max_papers: int = 2
    search_category: str = "cs.AI"
    download_max_retries: int = 3
    download_retry_delay_base: float = 5.0
    max_concurrent_downloads: int = 3
    max_concurrent_parsing: int = 1

    namespaces: dict = {
        "atom": "http://www.w3.org/2005/Atom",
        "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

class PDFParserSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="PDF_PARSER__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )
    max_pages: int = 30
    max_file_size_mb: int = 20
    do_ocr: bool = False
    do_table_structure: bool = False
    
class ChunkingSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="CHUNKING__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    chunk_size: int = 600  # Target words per chunk
    overlap_size: int = 100  # Words to overlap between chunks
    min_chunk_size: int = 100  # Minimum words for a valid chunk
    section_based: bool = True  # Use section-based chunking when available

class OpenSearchSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="OPENSEARCH__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    host: str = "http://localhost:9200"
    index_name: str = "arxiv-papers"
    chunk_index_suffix: str = "chunks"  # Creates single hybrid index: {index_name}-{suffix}
    max_text_size: int = 1000000

    # Vector search settings
    vector_dimension: int = 1024  # Jina embeddings dimension
    vector_space_type: str = "cosinesimil"  # cosinesimil, l2, innerproduct

    # Hybrid search settings
    rrf_pipeline_name: str = "hybrid-rrf-pipeline"
    hybrid_search_size_multiplier: int = 2  # Get k*multiplier for better recall
    
class EmbeddingSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )
    jina_api_key: str 
    base_url: str = "https://api.jina.ai/v1/embeddings"
    content_type: str = "application/json"
    timeout_seconds: int = 30
    embedding_model: str = "jina-embeddings-v3"
    embedding_passage_retrival_task: str = "retrieval.passage"
    embedding_query_retrival_task: str = "retrieval.query"
    dimensions: int = 1024
    embedding_batch_size:int = 100
    rate_limit_delay_seconds: float = 3.0  # Delay between Jina API calls to avoid 429s
    max_retries_on_rate_limit: int = 3
    retry_backoff_seconds: float = 20.0  # Fallback wait when Jina omits Retry-After
    
class AgentSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="AGENT__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    max_retrieval_retries: int = 2
    max_generation_retries: int = 1
    recursion_limit: int = 25

class RedisSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="REDIS__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    ttl_hours: int = 6

class LangfuseSettings(BaseConfigSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", str(ENV_FILE_PATH)],
        env_prefix="LANGFUSE__",
        extra="ignore",
        frozen=True,
        case_sensitive=False,
    )

    secret_key: str = ""
    public_key: str = ""
    base_url: str = "https://cloud.langfuse.com"
    enabled: bool = False

class Settings(BaseConfigSettings):
    app_version: str = "0.1.0"
    debug: bool = True
    environment: Literal["development", "staging", "production"] = "development"
    service_name: str = "rag-api"

    postgres_database_url: str
    postgres_echo_sql: bool = False
    postgres_pool_size: int = 5
    postgres_max_overflow: int = 0

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout: int = 300

    # LLM provider: "openai" or "bedrock"
    provider: str = "openai"

    redis_url: str = ""

    embedding: EmbeddingSettings = Field(default_factory = EmbeddingSettings)
    arxiv: ArxivSettings = Field(default_factory=ArxivSettings)
    pdf_parser: PDFParserSettings = Field(default_factory=PDFParserSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    opensearch: OpenSearchSettings = Field(default_factory=OpenSearchSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    langfuse: LangfuseSettings = Field(default_factory=LangfuseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)

    @field_validator("postgres_database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not (v.startswith("postgresql://") or v.startswith("postgresql+psycopg2://")):
            raise ValueError("Database URL must start with 'postgresql://' or 'postgresql+psycopg2://'")
        return v


def get_settings() -> Settings:
    return Settings()