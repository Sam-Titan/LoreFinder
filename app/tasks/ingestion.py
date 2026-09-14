import uuid
from datetime import datetime, timezone
from celery import Celery
from app.core.config import settings
from app.db import firestore, chroma
from app.services import ingest_service

celery_app = Celery(
    "dawn",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL
)

@celery_app.task(bind=True, max_retries=3)
def ingest_novel_task(self, doc_id: str, title: str, author: str):
    try:
        import asyncio
        asyncio.run(ingest_service.run_novel_ingestion(doc_id, title, author))
    except ValueError as e:
        # Permanent failure — novel not found, don't retry
        print(f"Permanent failure for {title}: {e}")
        from app.db import firestore
        firestore.update_status(doc_id, "failed")
        return  # no retry
    except Exception as e:
        # Transient failure — network, rate limit, etc — retry, unless this
        # was already the last allowed attempt, in which case give up cleanly
        # instead of leaving the doc stuck on "processing" forever.
        if self.request.retries >= self.max_retries:
            print(f"Giving up on {title} after {self.request.retries + 1} attempts: {e}")
            from app.db import firestore
            doc = firestore.get_document(doc_id)
            # Only mark it "failed" if chunks were never made ready — if this
            # was a background-summarization failure, the document is still
            # fully usable for narrow queries and shouldn't be hidden.
            if not doc or doc.get("phase", "start") == "start":
                firestore.update_status(doc_id, "failed")
            return
        raise self.retry(exc=e, countdown=30)
    
@celery_app.task(bind=True, max_retries=2)
def ingest_pdf_task(self, session_id: str, file_bytes: bytes):
    try:
        import asyncio
        asyncio.run(ingest_service.run_pdf_ingestion(session_id, file_bytes))
    except Exception as e:
        raise self.retry(exc=e, countdown=15)

@celery_app.task
def cleanup_stale_collections_task():
    stale_sessions = chroma.list_stale_collections(
        ttl_hours=settings.TTL_HOURS
    )
    for session_id in stale_sessions:
        try:
            chroma.delete_temp_collection(session_id)
            print(f"Deleted stale collection: temp_{session_id}")
        except Exception as e:
            print(f"Failed to delete temp_{session_id}: {e}")

# Celery beat schedule — runs cleanup every 30 minutes
celery_app.conf.beat_schedule = {
    "cleanup-stale-collections": {
        "task": "app.tasks.ingestion.cleanup_stale_collections_task",
        "schedule": 1800.0  # 30 minutes in seconds
    }
}

celery_app.conf.update(
    task_acks_late=True,              # only remove from queue after success
    task_reject_on_worker_lost=True   # requeue if worker dies mid-task
)