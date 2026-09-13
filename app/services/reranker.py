import threading

from sentence_transformers import CrossEncoder

_model = None
_model_lock = threading.Lock()

def get_reranker() -> CrossEncoder:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _model

def rerank(query: str, candidates: list[dict], top_k: int) -> list[dict]:
    if not candidates:
        return candidates
    model = get_reranker()
    pairs = [[query, c["document"]] for c in candidates]
    scores = model.predict(pairs)
    ranked = sorted(zip(candidates, scores, strict=True), key=lambda pair: pair[1], reverse=True)
    return [c for c, _ in ranked[:top_k]]
