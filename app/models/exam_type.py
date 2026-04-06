"""
MongoDB document model for exam type registry (JAMB, WAEC, etc.).

Stored in collection ``exam_types``. Subjects, exam papers, and questions
reference ``exam_type_id`` for filtering and joins.
"""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExamTypeDocument(Document):
    """
    One canonical exam body / exam type (e.g. JAMB, WAEC).

    ``code`` is the unique identifier, typically upper-case (e.g. ``JAMB``).
    """

    code: str = Field(
        ...,
        description="Unique short code, e.g. 'JAMB', 'WAEC'",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(None)

    class Settings:
        name = "exam_types"
        indexes = [
            IndexModel([("code", ASCENDING)], name="idx_code_unique", unique=True),
        ]
