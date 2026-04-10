from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.exam_file import ExamFileDocument


class ExamFileOut(BaseModel):
    id: str = Field(..., description="MongoDB document id")
    paper_id: str = Field(..., description="Parent ExamPaper document id")
    filename: str = Field(..., description="Client-provided filename at upload time")
    file_hash: str = Field(..., description="SHA-256 hex of the PDF bytes")
    file_url: Optional[str] = Field(None, description="Publicly accessible URL")
    size_bytes: int
    total_pages: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class ExamFileListResponse(BaseModel):
    items: List[ExamFileOut]
    total: int
    skip: int
    limit: int


def file_to_out(doc: ExamFileDocument) -> ExamFileOut:
    return ExamFileOut(
        id=str(doc.id),
        paper_id=str(doc.paper_id),
        filename=doc.filename,
        file_hash=doc.file_hash,
        file_url=doc.file_url,
        size_bytes=doc.size_bytes,
        total_pages=doc.total_pages,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
