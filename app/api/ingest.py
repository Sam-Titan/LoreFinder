import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.ingest_schema import IngestNovelRequest, IngestStatusResponse
from app.services.ingest_service import check_duplicate
from app.db import firestore
from app.tasks.ingestion import ingest_novel_task, ingest_pdf_task
from app.core.config import settings

router = APIRouter()

@router.post("/novel", response_model=IngestStatusResponse)
async def ingest_novel(payload: IngestNovelRequest):
    existing_doc_id = await check_duplicate(payload.novel_name, payload.author_name)
    if existing_doc_id:
        doc = firestore.get_document(existing_doc_id)
        status = doc.get("status")

        # Allow retry on failed
        if status == "failed":
            firestore.update_status(existing_doc_id, "pending")
            ingest_novel_task.delay(existing_doc_id, payload.novel_name, payload.author_name)
            return IngestStatusResponse(
                doc_id=existing_doc_id,
                status="pending",
                message="Previous attempt failed. Restarting ingestion."
            )

        # Recovery: stuck in processing > 10 min
        if status == "processing":
            ingested_at = doc.get("ingested_at")
            if ingested_at:
                elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(ingested_at)
                if elapsed > timedelta(minutes=10):
                    firestore.update_status(existing_doc_id, "pending")
                    ingest_novel_task.delay(existing_doc_id, payload.novel_name, payload.author_name)
                    return IngestStatusResponse(
                        doc_id=existing_doc_id,
                        status="pending",
                        message="Previous ingestion timed out. Restarted."
                    )

        return IngestStatusResponse(
            doc_id=existing_doc_id,
            status=status,
            message="Novel already exists. Use this doc_id to query."
        )
    
    # 2. Create Firestore document with pending status
    doc_id = f"doc_{uuid.uuid4().hex[:10]}"
    firestore.create_document(doc_id, {
        "doc_id": doc_id,
        "title": payload.novel_name,
        "author": payload.author_name,
        "source": None,
        "status": "pending",
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "embedding_model": settings.EMBEDDING_MODEL_NAME
    })

    # 3. Enqueue background task
    ingest_novel_task.delay(doc_id, payload.novel_name, payload.author_name)

    return IngestStatusResponse(
        doc_id=doc_id,
        status="pending",
        message="Novel ingestion started. Use /ingest/status to track progress."
    )

@router.post("/pdf", response_model=IngestStatusResponse)
async def ingest_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    session_id = f"session_{uuid.uuid4().hex[:10]}"
    file_bytes = await file.read()

    # Enqueue background task — no Firestore write for PDFs
    ingest_pdf_task.delay(session_id, file_bytes)

    return IngestStatusResponse(
        doc_id=session_id,
        status="pending",
        message="PDF ingestion started. Session expires after 2 hours of inactivity."
    )

@router.get("/status/{doc_id}", response_model=IngestStatusResponse)
async def ingest_status(doc_id: str):
    doc = firestore.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    return IngestStatusResponse(
        doc_id=doc_id,
        status=doc.get("status", "unknown"),
        message=f"Document is currently {doc.get('status', 'unknown')}.",
        progress=doc.get("progress", None)
    )