from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLMs
    GROQ_API_KEY: str
    GEMINI_API_KEY: str

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str

    # Chroma
    CHROMA_PERSIST_PATH: str = "./chroma_store"

    # Embedding
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

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