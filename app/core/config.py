from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLMs
    GROQ_API_KEY: str
    GEMINI_API_KEY: str

    # Firebase
    FIREBASE_CREDENTIALS_PATH: str

    # Chroma Cloud — tenant/database aren't always inferable from the API key
    # alone (this account's key needs both given explicitly, confirmed by a
    # live ChromaAuthError otherwise), so all three are required.
    CHROMA_API_KEY: str
    CHROMA_TENANT: str
    CHROMA_DATABASE: str

    # Embedding
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"

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