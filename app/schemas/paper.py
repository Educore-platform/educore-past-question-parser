from datetime import datetime
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.exam_file import ExamFileDocument
from app.models.exam_paper import ExamPaperDocument


class ExamPaperOut(BaseModel):
    id: str = Field(..., description="MongoDB document id")
    subject_id: Optional[str] = None
    subject: str
    exam_type_id: Optional[str] = None
    exam_type: str = Field(..., alias="examType")
    paper_code: Optional[str] = Field(None, description="Subject-scoped upload sequence")
    year: Optional[int] = Field(None, description="Primary year (first entry in years_detected)")
    years_detected: List[int]
    total_questions: int
    exam_file_id: Optional[str] = Field(None, description="Linked ExamFile document id")
    filename: Optional[str] = Field(None, description="Original PDF filename at upload time")
    size_bytes: Optional[int] = None
    total_pages: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class ExamPaperListResponse(BaseModel):
    items: List[ExamPaperOut]
    total: int
    skip: int
    limit: int


def paper_to_out(
    doc: ExamPaperDocument,
    *,
    subjects: Optional[Dict[PydanticObjectId, str]] = None,
    exam_types: Optional[Dict[PydanticObjectId, str]] = None,
    exam_file: Optional[ExamFileDocument] = None,
) -> ExamPaperOut:
    subject_name = ""
    if doc.subject_id and subjects is not None:
        subject_name = subjects.get(doc.subject_id) or ""
    exam_code = ""
    if doc.exam_type_id and exam_types is not None:
        exam_code = exam_types.get(doc.exam_type_id) or ""
    primary_year = doc.years_detected[0] if doc.years_detected else None
    return ExamPaperOut(
        id=str(doc.id),
        subject_id=str(doc.subject_id) if doc.subject_id else None,
        subject=subject_name,
        exam_type_id=str(doc.exam_type_id) if doc.exam_type_id else None,
        examType=exam_code,
        paper_code=doc.paper_code,
        year=primary_year,
        years_detected=doc.years_detected,
        total_questions=doc.total_questions,
        exam_file_id=str(exam_file.id) if exam_file else None,
        filename=exam_file.filename if exam_file else None,
        size_bytes=exam_file.size_bytes if exam_file else None,
        total_pages=exam_file.total_pages if exam_file else 0,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
