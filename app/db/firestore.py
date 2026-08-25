import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import settings
from google.cloud.firestore_v1.base_query import FieldFilter
from thefuzz import fuzz

_db = None

def get_client():
    global _db
    if _db is None:
        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
        _db = firestore.client()
    return _db

def create_document(doc_id: str, data: dict):
    db = get_client()
    db.collection("documents").document(doc_id).set(data)

def get_document(doc_id: str) -> dict | None:
    db = get_client()
    doc = db.collection("documents").document(doc_id).get()
    return doc.to_dict() if doc.exists else None

def update_status(doc_id: str, status: str):
    db = get_client()
    db.collection("documents").document(doc_id).update({"status": status})

def check_exists(title: str, author: str) -> str | None:
    db = get_client()
    docs = db.collection("documents").stream()
    for doc in docs:
        data = doc.to_dict()
        title_score = fuzz.ratio(title.lower(), data.get("title", "").lower())
        author_score = fuzz.ratio(author.lower(), data.get("author", "").lower())
        if title_score >= 85 and author_score >= 85:
            return doc.id
    return None

def write_chunk(doc_id: str, chunk: dict):
    db = get_client()
    chunk_id = chunk["chunk_id"]
    (
        db.collection("documents")
        .document(doc_id)
        .collection("chunks")
        .document(chunk_id)
        .set(chunk)
    )

def write_chapter(doc_id: str, chapter: dict):
    db = get_client()
    chapter_id = chapter["chapter_id"]
    (
        db.collection("documents")
        .document(doc_id)
        .collection("chapters")
        .document(chapter_id)
        .set(chapter)
    )

def get_chapters(doc_id: str) -> list[dict]:
    db = get_client()
    docs = (
        db.collection("documents")
        .document(doc_id)
        .collection("chapters")
        .order_by("chapter_number")
        .stream()
    )
    return [doc.to_dict() for doc in docs]

def get_chunks_by_ids(doc_id: str, chunk_ids: list[str]) -> list[dict]:
    db = get_client()
    # TODO: batch if > 30
    docs = (
        db.collection("documents")
        .document(doc_id)
        .collection("chunks")
        .where(filter=FieldFilter("chunk_id", "in", chunk_ids))
        .stream()
    )
    return [doc.to_dict() for doc in docs]