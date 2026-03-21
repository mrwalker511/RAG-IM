from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://rag:rag@localhost:5432/rag_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Embeddings
    EMBEDDING_PROVIDER: str = "openai"  # openai | sentence_transformer
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536

    # LLM
    LLM_PROVIDER: str = "openai"  # openai | litellm
    LLM_MODEL: str = "gpt-4o-mini"

    # Chunking defaults
    DEFAULT_CHUNK_SIZE: int = 512
    DEFAULT_CHUNK_OVERLAP: int = 64
    DEFAULT_TOP_K: int = 5

    # Retrieval
    RERANK_TOP_N: int = 20
    BM25_STALE_AFTER_MINUTES: int = 60

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000


settings = Settings()
