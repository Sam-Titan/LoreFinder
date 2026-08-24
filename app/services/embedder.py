from abc import ABC, abstractmethod
from sentence_transformers import SentenceTransformer
from app.core.config import settings

class EmbedderInterface(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        pass

class LocalEmbedder(EmbedderInterface):
    def __init__(self):
        self._model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()

def get_embedder() -> EmbedderInterface:
    return LocalEmbedder()