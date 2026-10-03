import re

from rank_bm25 import BM25Okapi

from app.db import chroma

_indexes: dict[str, dict] = {}

def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())

def _build_chunk_index(doc_id: str) -> dict | None:
    collection = chroma.get_chunk_collection(doc_id)
    data = collection.get(include=["documents", "metadatas"])
    if not data["documents"]:
        # No chunks — e.g. an unknown/never-ingested doc_id (get_or_create_collection
        # silently creates an empty one). BM25Okapi([]) raises ZeroDivisionError, so
        # short-circuit instead: no chunks means no lexical matches, not an error.
        return None
    tokenized = [_tokenize(doc) for doc in data["documents"]]
    return {
        "bm25": BM25Okapi(tokenized),
        "ids": data["ids"],
        "documents": data["documents"],
        "metadatas": data["metadatas"],
    }

def invalidate(doc_id: str) -> None:
    # Drop a cached index (possibly built as empty, e.g. against a Chroma
    # collection that was later repopulated) so the next search rebuilds it.
    _indexes.pop(doc_id, None)

def search_chunks(
    doc_id: str, query: str, top_k: int, chapter_numbers: list[int] = None
) -> list[dict]:
    # Built once per process and reused — a doc's chunks never change after ingestion,
    # so no cache invalidation is needed for the lifetime of a worker/uvicorn process.
    if doc_id not in _indexes:
        _indexes[doc_id] = _build_chunk_index(doc_id)
    idx = _indexes[doc_id]
    if idx is None:
        return []

    scores = idx["bm25"].get_scores(_tokenize(query))
    candidate_indices = range(len(scores))
    if chapter_numbers:
        chapter_set = set(chapter_numbers)
        candidate_indices = [
            i for i in candidate_indices
            if idx["metadatas"][i].get("chapter_number") in chapter_set
        ]
    ranked = sorted(candidate_indices, key=lambda i: scores[i], reverse=True)[:top_k]

    return [
        {
            "id": idx["ids"][i],
            "document": idx["documents"][i],
            "metadata": idx["metadatas"][i],
            "score": float(scores[i]),  # BM25: higher is more relevant
        }
        for i in ranked
    ]
