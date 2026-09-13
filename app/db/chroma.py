import threading
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from datetime import datetime, timezone

_client = None
_client_lock = threading.Lock()

def get_client():
    global _client
    # Now that query handling runs across executor threads (not just Celery's
    # separate worker processes), the lazy check-then-create below is a real
    # race: two threads can both see _client is None and both construct a
    # PersistentClient concurrently, corrupting Chroma's Rust bindings state.
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = chromadb.PersistentClient(
                    path=settings.CHROMA_PERSIST_PATH,
                    settings=ChromaSettings(anonymized_telemetry=False)
                )
    return _client

def get_chunk_collection(doc_id: str):
    return get_client().get_or_create_collection(f"{doc_id}_chunks")

def get_chapter_collection(doc_id: str):
    return get_client().get_or_create_collection(f"{doc_id}_chapters")

def get_temp_collection(session_id: str):
    return get_client().get_or_create_collection(f"temp_{session_id}")

def write_chunk_embeddings(doc_id: str, chunks: list[dict], vectors: list[list[float]]):
    collection = get_chunk_collection(doc_id)
    # upsert (not add) — chunk_id is deterministic, so a retried ingestion
    # overwrites in place instead of erroring or duplicating.
    collection.upsert(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=vectors,
        documents=[c["chunk_text"] for c in chunks],
        metadatas=[{
            "doc_id": doc_id,
            "chapter_number": c["chapter_number"],
            "chapter_title": c.get("chapter_title") or "",  # add this
            "chunk_index": c["chunk_index"]
        } for c in chunks]
    )

def write_chapter_embeddings(doc_id: str, chapters: list[dict], vectors: list[list[float]]):
    collection = get_chapter_collection(doc_id)
    # upsert (not add) — chapter_id is deterministic, so a retried summarization
    # pass overwrites in place instead of erroring or duplicating.
    collection.upsert(
        ids=[c["chapter_id"] for c in chapters],
        embeddings=vectors,
        documents=[c["summary"] for c in chapters],
        metadatas=[{
            "doc_id": doc_id,
            "chapter_number": c["chapter_number"],
            "chapter_index": c["chapter_number"]
        } for c in chapters]
    )

def write_temp_embeddings(session_id: str, chunks: list[dict], vectors: list[list[float]]):
    collection = get_temp_collection(session_id)
    now = datetime.now(timezone.utc).timestamp()
    collection.add(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=vectors,
        documents=[c["chunk_text"] for c in chunks],
        metadatas=[{
            "session_id": session_id,
            "chunk_index": c["chunk_index"],
            "last_accessed": now   # set here, not from chunk
        } for c in chunks]
    )

def search_chunks(
    doc_id: str,
    query_vectors: list[list[float]],
    top_k: int,
    chapter_numbers: list[int] = None
) -> list[list[dict]]:
    collection = get_chunk_collection(doc_id)
    query_kwargs = {
    "query_embeddings": query_vectors,
    "n_results": top_k
    }
    if chapter_numbers:
        query_kwargs["where"] = {"chapter_number": {"$in": chapter_numbers}}

    results = collection.query(**query_kwargs)
    return _format_results_multi(results)

def search_chapters(doc_id: str, query_vectors: list[list[float]], top_n: int) -> list[list[dict]]:
    collection = get_chapter_collection(doc_id)
    results = collection.query(
        query_embeddings=query_vectors,
        n_results=top_n
    )
    return _format_results_multi(results)

def search_temp(session_id: str, query_vectors: list[list[float]], top_k: int) -> list[list[dict]]:
    collection = get_temp_collection(session_id)
    results = collection.query(
        query_embeddings=query_vectors,
        n_results=top_k
    )
    return _format_results_multi(results)

def delete_temp_collection(session_id: str):
    get_client().delete_collection(f"temp_{session_id}")

def list_stale_collections(ttl_hours: int) -> list[str]:
    from datetime import datetime, timezone
    client = get_client()
    stale = []
    for col in client.list_collections():
        if not col.name.startswith("temp_"):
            continue
        results = col.get(limit=1, include=["metadatas"])
        if results["metadatas"]:
            last = results["metadatas"][0].get("last_accessed", 0)
            age = (datetime.now(timezone.utc).timestamp() - last) / 3600
            if age > ttl_hours:
                stale.append(col.name.replace("temp_", ""))
    return stale

def _format_results_multi(results: dict) -> list[list[dict]]:
    all_formatted = []
    for qi in range(len(results["ids"])):
        formatted = []
        for i, doc_id in enumerate(results["ids"][qi]):
            formatted.append({
                "id": doc_id,
                "document": results["documents"][qi][i],
                "metadata": results["metadatas"][qi][i],
                "score": results["distances"][qi][i] if "distances" in results else None
            })
        all_formatted.append(formatted)
    return all_formatted