"""
MongoDB document model for exam paper imports.

Stored in collection `exam_papers`. One document per uploaded PDF.
Logical import for one past-paper PDF: subject/year context and question
counts. File bytes and storage metadata live in ``exam_files`` (see
``ExamFileDocument``) linked by ``paper_id``.
"""

from datetime import datetime, timezone
from typing import List, Optional

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExamPaperDocument(Document):
    """
    Parent record for all questions extracted from one PDF import.

    ``paper_code`` is a subject-scoped sequence string ("001", "002", …)
    assigned at import time so different uploads of the same subject can be
    distinguished in the UI.
    """

    subject_id: Optional[PydanticObjectId] = Field(
        None,
        description="Reference to SubjectDocument._id",
    )
    paper_code: Optional[str] = Field(
        None,
        description="Subject-scoped upload sequence, e.g. '001', '002'",
    )
    exam_type_id: Optional[PydanticObjectId] = Field(
        None,
        description="Reference to ExamTypeDocument._id",
    )
    year: Optional[str] = Field(
        None,
        description="Primary year detected in the paper",
    )
    years_detected: List[str] = Field(
        default_factory=list,
        description="All distinct years found across questions in this paper",
    )
    total_questions: int = Field(
        0,
        description="Number of questions extracted and stored from this paper",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(None)

    class Settings:
        name = "exam_papers"
        indexes = [
            IndexModel(
                [("subject_id", ASCENDING), ("year", ASCENDING)],
                name="idx_subject_year",
            ),
            IndexModel(
                [("exam_type_id", ASCENDING), ("subject_id", ASCENDING)],
                name="idx_examtype_subject",
            ),
            IndexModel([("exam_type_id", ASCENDING)], name="idx_exam_type_id"),
            IndexModel([("subject_id", ASCENDING)], name="idx_subject_id"),
            IndexModel([("created_at", DESCENDING)], name="idx_created_desc"),
        ]
