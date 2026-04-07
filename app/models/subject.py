"""
MongoDB document model for the subject registry.

Stored in collection `subjects`. One document per canonical subject per exam
type (e.g. JAMB "Mathematics" and WAEC "Mathematics" are separate entries).
``name`` is normalized (stripped, title-cased). The unique constraint is the
compound ``(name, exam_type_id)`` pair — the same subject name may appear
for different exam types. Each subject links to one ``ExamTypeDocument`` via
``exam_type_id``.
"""

from datetime import datetime, timezone
from typing import List, Optional

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, IndexModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SubjectDocument(Document):
    """
    Canonical subject registry entry.

    Uniqueness is on the compound ``(name, exam_type_id)`` pair so the same
    subject name can exist independently per exam type.
    """

    name: str = Field(
        ...,
        description="Canonical subject name (e.g. 'Government'), unique per exam type",
    )
    exam_type_id: Optional[PydanticObjectId] = Field(
        None,
        description="Reference to ExamTypeDocument._id",
    )
    aliases: List[str] = Field(
        default_factory=list,
        description="Alternate spellings found in PDFs that resolved to this subject",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(None)

    class Settings:
        name = "subjects"
        indexes = [
            IndexModel(
                [("name", ASCENDING), ("exam_type_id", ASCENDING)],
                name="idx_name_examtype_unique",
                unique=True,
            ),
            IndexModel([("exam_type_id", ASCENDING)], name="idx_exam_type_id"),
        ]
