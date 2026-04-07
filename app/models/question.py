"""
MongoDB document model for extracted exam questions.

Stored in collection `questions`. Each document belongs to one exam paper
via ``paper_id`` and ``subject_id`` / ``exam_type_id``. File-level metadata
(filename, hash, page count, paper_code) lives in ``exam_papers``.
"""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field, field_validator
from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QuestionDocument(Document):
    """
    One multiple-choice (or similar) question extracted from a PDF.

    Provenance: each row links to one ``ExamPaperDocument`` via ``paper_id``
    and to one ``SubjectDocument`` via ``subject_id``.

    ``subject_id`` and ``exam_type_id`` are intentionally denormalised from
    the parent ``ExamPaperDocument`` to allow efficient single-collection
    filtering without a join. Keep them in sync when subjects are reassigned.
    """

    paper_id: Optional[PydanticObjectId] = Field(
        None,
        description="Reference to ExamPaperDocument._id (shared by all questions from one PDF)",
    )
    subject_id: Optional[PydanticObjectId] = Field(
        None,
        description="Reference to SubjectDocument._id (denormalised for query performance)",
    )
    exam_type_id: Optional[PydanticObjectId] = Field(
        None,
        description="Reference to ExamTypeDocument._id (denormalised for query performance)",
    )
    year: Optional[int] = Field(
        None,
        description="Exam year as an integer (e.g. 2019)",
    )
    question_number: int = Field(..., ge=1, description="Number within that paper/section")
    question: str = Field(..., description="Question stem / prompt text")
    question_latex: Optional[str] = Field(
        None,
        description="LaTeX fragment for the stem when it contains fractions or math symbols",
    )
    options: dict[str, str] = Field(
        default_factory=dict,
        description="Map of option label to text, e.g. {'A': '...', 'B': '...'}",
    )
    options_latex: dict[str, str] = Field(
        default_factory=dict,
        description="Per-option LaTeX fragments (only keys that need math rendering)",
    )
    answer: Optional[str] = Field(None, description="Correct option key when parsed, e.g. 'A'")
    explanation: Optional[str] = Field(None, description="Optional explanation")
    is_flagged: bool = Field(False, description="Whether this question is flagged for review")
    flag_comment: Optional[str] = Field(None, description="Optional comment when flagged")
    image_url: Optional[str] = Field(
        None,
        description="Relative URL of the diagram image for this question",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(None)

    model_config = {"populate_by_name": True}

    class Settings:
        name = "questions"
        indexes = [
            IndexModel(
                [
                    ("exam_type_id", ASCENDING),
                    ("subject_id", ASCENDING),
                    ("year", ASCENDING),
                    ("question_number", ASCENDING),
                ],
                name="exam_subject_year_qnum",
            ),
            IndexModel([("paper_id", ASCENDING)], name="idx_paper_id"),
            IndexModel([("subject_id", ASCENDING)], name="idx_subject_id"),
            IndexModel([("exam_type_id", ASCENDING)], name="idx_exam_type_id"),
            IndexModel(
                [("subject_id", ASCENDING), ("year", ASCENDING)],
                name="idx_subject_year",
            ),
            IndexModel([("created_at", DESCENDING)], name="idx_created_desc"),
            IndexModel([("is_flagged", ASCENDING)], name="idx_is_flagged"),
            IndexModel([("question", TEXT)], name="idx_question_text"),
        ]

    @field_validator("options", mode="before")
    @classmethod
    def normalize_options(cls, v: object) -> dict[str, str]:
        if not v or not isinstance(v, dict):
            return {}
        return {str(k): str(val).strip() for k, val in v.items()}
