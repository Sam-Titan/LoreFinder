import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import settings
from google.cloud.firestore_v1.base_query import FieldFilter

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
    docs = (
        db.collection("documents")
        .where(filter=FieldFilter("title", "==", title))
        .where(filter=FieldFilter("author", "==", author))
        .limit(1)
        .stream()
    )
    for doc in docs:
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

# TODO: batch if > 30
def get_chunks_by_indexes(doc_id: str, chunk_indexes: list[int]) -> list[dict]:
    db = get_client()
    docs = (
        db.collection("documents")
        .document(doc_id)
        .collection("chunks")
        .where(filter=FieldFilter("chunk_index", "in", chunk_indexes))
        .stream()
    )
    return [doc.to_dict() for doc in docs]