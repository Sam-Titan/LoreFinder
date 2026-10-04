from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLMs
    GROQ_API_KEY: str
    GEMINI_API_KEY: str

    # Jina AI — hosted embeddings + reranking (replaces local
    # sentence-transformers/torch, which needed ~1GB+ RAM the app's Render
    # tier doesn't have headroom for).
    JINA_API_KEY: str

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str

    # Chroma Cloud — tenant/database aren't always inferable from the API key
    # alone (this account's key needs both given explicitly, confirmed by a
    # live ChromaAuthError otherwise), so all three are required.
    CHROMA_API_KEY: str
    CHROMA_TENANT: str
    CHROMA_DATABASE: str

    # Embedding / reranking (Jina AI hosted models)
    EMBEDDING_MODEL_NAME: str = "jina-embeddings-v3"
    # 768 of the model's max 1024 dims (Matryoshka-truncatable) — near-identical
    # retrieval quality per Jina's own benchmarks, smaller Chroma storage/bandwidth.
    EMBEDDING_DIMENSIONS: int = 768
    RERANKER_MODEL_NAME: str = "jina-reranker-v3.5"

    # Groq and Gemini Model Names
    GROQ_MODEL_NAME: str = "openai/gpt-oss-20b"
    GEMINI_MODEL_NAME: str = "gemini-3.5-flash-lite"
    
    # Celery + Redis
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    REDIS_URL: str = "redis://localhost:6379/1"

    # Ingestion tuning
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    TTL_HOURS: int = 2

    class Config:
        env_file = ".env"

settings = Settings()