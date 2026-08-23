from pydantic import BaseModel
from typing import Optional, Literal

# User Query Schema
class Novel_Query(BaseModel):
    novel_name: str
    author_name: str

# Novel Status
class Novel_Status(BaseModel):
    doc_id: str
    status: str
    message: str

# Actual Query
class UserQuery(BaseModel):
    doc_id: str
    query: str

# Citations
class Citations(BaseModel):
    chapter_number: int
    chapter_title: Optional[str]
    chunk_index: int

# Query Response
class System_Query_Response(BaseModel):
    doc_id: str
    query: str
    response: str
    references: list[Citations]
    
# Category: Broad or Narrow
class Category(BaseModel):
    category: Literal["broad", "narrow"]

class RetrievalResult(BaseModel):
    chunk_id: str
    chunk_text: str
    chapter_number: int
    chapter_title: Optional[str]
    chunk_index: int
    score: Optional[float]