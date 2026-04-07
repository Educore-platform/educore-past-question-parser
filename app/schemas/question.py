from datetime import datetime
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.question import QuestionDocument


class QuestionUpdate(BaseModel):
    """Fields to update an existing question. All fields are optional."""

    exam_type_id: Optional[str] = Field(None, description="ExamType document id")
    exam_type: Optional[str] = Field(None, alias="examType")
    subject_id: Optional[str] = Field(None, description="Subject document id")
    year: Optional[int] = None
    question_number: Optional[int] = None
    question: Optional[str] = None
    question_latex: Optional[str] = None
    options: Optional[Dict[str, str]] = None
    options_latex: Optional[Dict[str, str]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    image_url: Optional[str] = None
    is_flagged: Optional[bool] = None
    flag_comment: Optional[str] = None

    model_config = {"populate_by_name": True}


class QuestionOut(BaseModel):
    """Single question as returned by the API."""

    id: str = Field(..., description="MongoDB document id")
    paper_id: Optional[str] = Field(None, description="Parent ExamPaper id")
    subject_id: Optional[str] = Field(None, description="Parent Subject id")
    exam_type_id: Optional[str] = Field(None, description="ExamType document id")
    exam_type: str = Field(..., alias="examType")
    subject: str
    paper_code: Optional[str] = Field(None, description="Subject-scoped upload sequence, e.g. '001'")
    paper_name: Optional[str] = Field(None, description="Combination of subject and paper_code, e.g. 'Mathematics 001'")
    year: Optional[int] = None
    question_number: int
    question: str
    question_latex: Optional[str] = None
    options: Dict[str, str]
    options_latex: Dict[str, str] = Field(default_factory=dict)
    answer: Optional[str]
    explanation: Optional[str]
    is_flagged: bool = False
    flag_comment: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class QuestionListResponse(BaseModel):
    """Paginated list of questions with total count for the current filter."""

    items: List[QuestionOut]
    total: int
    skip: int
    limit: int


class QuestionSummaryOut(BaseModel):
    """Question row for catalog views: identity and exam metadata only (no stem or options)."""

    id: str = Field(..., description="MongoDB document id")
    paper_id: Optional[str] = Field(None, description="Parent ExamPaper id")
    subject_id: Optional[str] = Field(None, description="Parent Subject id")
    exam_type_id: Optional[str] = Field(None, description="ExamType document id")
    exam_type: str = Field(..., alias="examType")
    subject: str
    paper_code: Optional[str] = Field(None, description="Subject-scoped upload sequence, e.g. '001'")
    paper_name: Optional[str] = Field(None, description="Combination of subject and paper_code, e.g. 'Mathematics 001'")
    year: Optional[int] = Field(None, description="Year of the exam")
    question_number: int
    has_answer: bool = Field(..., description="Whether a correct option key was stored")
    has_image: bool = Field(..., description="Whether a diagram URL is attached")
    is_flagged: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class QuestionSummaryListResponse(BaseModel):
    """Paginated summaries without full question bodies."""

    items: List[QuestionSummaryOut]
    total: int
    skip: int
    limit: int


def question_to_out(
    doc: QuestionDocument,
    *,
    subjects: Optional[Dict[PydanticObjectId, str]] = None,
    exam_types: Optional[Dict[PydanticObjectId, str]] = None,
    paper_codes: Optional[Dict[PydanticObjectId, str]] = None,
) -> QuestionOut:
    subject_name = ""
    if doc.subject_id and subjects is not None:
        subject_name = subjects.get(doc.subject_id) or ""
    exam_code = ""
    if doc.exam_type_id and exam_types is not None:
        exam_code = exam_types.get(doc.exam_type_id) or ""
    paper_code = ""
    if doc.paper_id and paper_codes is not None:
        paper_code = paper_codes.get(doc.paper_id) or ""
    paper_name = f"{subject_name} {paper_code}".strip() if (subject_name or paper_code) else None
    return QuestionOut(
        id=str(doc.id),
        paper_id=str(doc.paper_id) if doc.paper_id else None,
        subject_id=str(doc.subject_id) if doc.subject_id else None,
        exam_type_id=str(doc.exam_type_id) if doc.exam_type_id else None,
        examType=exam_code,
        subject=subject_name,
        paper_code=paper_code or None,
        paper_name=paper_name,
        year=doc.year,
        question_number=doc.question_number,
        question=doc.question,
        question_latex=doc.question_latex,
        options=doc.options,
        options_latex=dict(doc.options_latex) if doc.options_latex else {},
        answer=doc.answer,
        explanation=doc.explanation,
        is_flagged=doc.is_flagged,
        flag_comment=doc.flag_comment,
        image_url=doc.image_url,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


def question_to_summary_out(
    doc: QuestionDocument,
    *,
    subjects: Optional[Dict[PydanticObjectId, str]] = None,
    exam_types: Optional[Dict[PydanticObjectId, str]] = None,
    paper_codes: Optional[Dict[PydanticObjectId, str]] = None,
) -> QuestionSummaryOut:
    subject_name = ""
    if doc.subject_id and subjects is not None:
        subject_name = subjects.get(doc.subject_id) or ""
    exam_code = ""
    if doc.exam_type_id and exam_types is not None:
        exam_code = exam_types.get(doc.exam_type_id) or ""
    paper_code = ""
    if doc.paper_id and paper_codes is not None:
        paper_code = paper_codes.get(doc.paper_id) or ""
    paper_name = f"{subject_name} {paper_code}".strip() if (subject_name or paper_code) else None
    return QuestionSummaryOut(
        id=str(doc.id),
        paper_id=str(doc.paper_id) if doc.paper_id else None,
        subject_id=str(doc.subject_id) if doc.subject_id else None,
        exam_type_id=str(doc.exam_type_id) if doc.exam_type_id else None,
        examType=exam_code,
        subject=subject_name,
        paper_code=paper_code or None,
        paper_name=paper_name,
        year=doc.year,
        question_number=doc.question_number,
        has_answer=doc.answer is not None,
        has_image=bool(doc.image_url),
        is_flagged=doc.is_flagged,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
