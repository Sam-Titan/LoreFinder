from app.core.config import settings
from app.services.jina_client import post_with_retry

_JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"

def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    if not candidates:
        return candidates

    response = post_with_retry(
        _JINA_RERANK_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.JINA_API_KEY}",
        },
        json_body={
            "model": settings.RERANKER_MODEL_NAME,
            "query": query,
            "top_n": min(top_k, len(candidates)),
            "documents": [c["document"] for c in candidates],
        },
        timeout=30,
    )
    # Jina already returns results sorted by relevance_score, descending.
    return [candidates[r["index"]] for r in response.json()["results"]]
