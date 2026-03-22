from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://rag:rag@localhost:5432/rag_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Embeddings
    EMBEDDING_PROVIDER: str = "sentence_transformer"  # openai | sentence_transformer
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384  # 384 for sentence_transformer (all-MiniLM-L6-v2), 1536 for openai

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
    UPLOAD_TMP_DIR: str = "/tmp"

    # CORS — comma-separated list of allowed origins; "*" allows all (dev only)
    CORS_ORIGINS: str = "*"

    # Rate limiting — requests per minute per API key (0 = disabled)
    RATE_LIMIT_PER_MINUTE: int = 60

    # DB connection pool
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # Redis connection pool
    REDIS_MAX_CONNECTIONS: int = 20

    # Query result cache TTL in seconds (0 = disabled)
    QUERY_CACHE_TTL: int = 300

    # Bootstrap auth/project seeding for fresh deployments
    BOOTSTRAP_PROJECT_NAME: str = ""
    BOOTSTRAP_API_KEY: str = ""
    BOOTSTRAP_API_KEY_LABEL: str = "bootstrap"


settings = Settings()
