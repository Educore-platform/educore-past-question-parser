from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.exam_file import ExamFileDocument


class ExamFileOut(BaseModel):
    id: str = Field(..., description="MongoDB document id")
    paper_id: str = Field(..., description="Parent ExamPaper document id")
    source_original_filename: str
    stored_filename: str
    relative_path: str
    file_hash: str = Field(..., description="SHA-256 hex of the PDF bytes")
    size_bytes: int
    total_pages: int
    content_type: str
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
        source_original_filename=doc.source_original_filename,
        stored_filename=doc.stored_filename,
        relative_path=doc.relative_path,
        file_hash=doc.file_hash,
        size_bytes=doc.size_bytes,
        total_pages=doc.total_pages,
        content_type=doc.content_type,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
