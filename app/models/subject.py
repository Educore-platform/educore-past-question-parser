"""
MongoDB document model for the subject registry.

Stored in collection `subjects`. One document per canonical subject
(e.g. "Government", "Biology"). ``name`` is the unique key — it is stored
in a normalized (stripped, title-cased) form and used for upsert / lookup
during extraction. Each subject links to one ``ExamTypeDocument`` via
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

    ``name`` is the unique display identifier (e.g. "Government").
    """

    name: str = Field(
        ...,
        description="Canonical subject name, unique (e.g. 'Government')",
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
            IndexModel([("name", ASCENDING)], name="idx_name_unique", unique=True),
            IndexModel([("exam_type_id", ASCENDING)], name="idx_exam_type_id"),
        ]
