from abc import ABC, abstractmethod

from app.core.config import settings
from app.services.jina_client import post_with_retry

_JINA_EMBEDDINGS_URL = "https://api.jina.ai/v1/embeddings"
# Jina's free tier caps at 100,000 tokens/minute. At this app's default chunk
# size (~800 words, ~1,000+ tokens), a 100-text batch alone can approach or
# exceed that ceiling in a single call (confirmed empirically — Jina's own
# 429 body says "reduce batch sizes"). 20 texts/batch keeps a single call
# comfortably under the limit even for longer chunks; post_with_retry still
# handles the inevitable 429s from a long novel's cumulative token volume
# across many batches.
_BATCH_SIZE = 20

class EmbedderInterface(ABC):
    @abstractmethod
    def embed(self, texts: list[str], task: str = "retrieval.passage") -> list[list[float]]:
        pass

class JinaEmbedder(EmbedderInterface):
    def __init__(self):
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.JINA_API_KEY}",
        }

    def embed(self, texts: list[str], task: str = "retrieval.passage") -> list[list[float]]:
        # task distinguishes indexed content ("retrieval.passage": chunk/chapter
        # text at ingest time) from search input ("retrieval.query": user
        # questions) — Jina's embeddings are asymmetric, so using the wrong
        # task for either side measurably hurts retrieval quality.
        if not texts:
            return []

        vectors: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i:i + _BATCH_SIZE]
            response = post_with_retry(
                _JINA_EMBEDDINGS_URL,
                headers=self._headers,
                json_body={
                    "model": settings.EMBEDDING_MODEL_NAME,
                    "task": task,
                    "dimensions": settings.EMBEDDING_DIMENSIONS,
                    "input": batch,
                },
                timeout=60,
            )
            data = sorted(response.json()["data"], key=lambda d: d["index"])
            vectors.extend(d["embedding"] for d in data)
        return vectors

def get_embedder() -> EmbedderInterface:
    return JinaEmbedder()
