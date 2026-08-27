import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from datetime import datetime, timezone

_client = None

def get_client():
    global _client
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
    collection.add(
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
    collection.add(
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

def search_chunks(doc_id: str, query_vector: list[float], top_k: int, chapter_numbers: list[int] = None) -> list[dict]:
    collection = get_chunk_collection(doc_id)
    query_kwargs = {
    "query_embeddings": [query_vector],
    "n_results": top_k
    }
    if chapter_numbers:
        query_kwargs["where"] = {"chapter_number": {"$in": chapter_numbers}}

    results = collection.query(**query_kwargs)
    return _format_results(results)

def search_chapters(doc_id: str, query_vector: list[float], top_n: int) -> list[dict]:
    collection = get_chapter_collection(doc_id)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_n
    )
    return _format_results(results)

def search_temp(session_id: str, query_vector: list[float], top_k: int) -> list[dict]:
    collection = get_temp_collection(session_id)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k
    )
    return _format_results(results)

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

def _format_results(results: dict) -> list[dict]:
    formatted = []
    for i, doc_id in enumerate(results["ids"][0]):
        formatted.append({
            "id": doc_id,
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "score": results["distances"][0][i] if "distances" in results else None
        })
    return formatted