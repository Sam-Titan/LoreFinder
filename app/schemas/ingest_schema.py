from pydantic import BaseModel
from typing import Optional

class IngestNovelRequest(BaseModel):
    novel_name: str
    author_name: str

class IngestPDFRequest(BaseModel):
    # File itself is handled via FastAPI's UploadFile, not Pydantic
    # This schema is for any additional metadata sent alongside the file
    session_id: Optional[str] = None  # auto-generated if not provided

class IngestStatusResponse(BaseModel):
    doc_id: str
    status: str        # "pending" | "ready" | "failed"
    message: str
    progress: Optional[str] = None  # e.g. "chunks written, summarization pending"