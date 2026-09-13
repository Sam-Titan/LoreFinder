from pydantic import BaseModel, Field
from typing import Optional

class IngestNovelRequest(BaseModel):
    novel_name: str = Field(..., min_length=1, max_length=200)
    author_name: str = Field(..., min_length=1, max_length=200)

class IngestPDFRequest(BaseModel):
    # File itself is handled via FastAPI's UploadFile, not Pydantic
    # This schema is for any additional metadata sent alongside the file
    session_id: Optional[str] = None  # auto-generated if not provided

class IngestStatusResponse(BaseModel):
    doc_id: str
    status: str        # "pending" | "ready" | "failed"
    message: str
    progress: Optional[str] = None  # e.g. "chunks written, summarization pending"