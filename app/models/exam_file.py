"""
MongoDB document model for uploaded exam PDF files.

Stored in collection ``exam_files``. One row per source file; ``paper_id``
points at the logical ``ExamPaperDocument`` that owns extracted questions.

The uploaded file is removed from disk after the extraction pipeline
completes. This document retains only the identity metadata that has
durable value: the original filename, the SHA-256 hash (idempotency key),
the byte size, and the page count.
"""

from datetime import datetime, timezone
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExamFileDocument(Document):
    """
    Metadata for one uploaded PDF tied to an exam paper import.

    ``file_hash`` (SHA-256 hex) is unique and used for idempotency lookups.
    """

    paper_id: PydanticObjectId = Field(
        ...,
        description="Reference to ExamPaperDocument._id",
    )
    filename: str = Field(
        ...,
        description="Client-provided filename at upload time",
    )
    file_hash: str = Field(
        ...,
        description="Lowercase hex SHA-256 of the PDF bytes; idempotency key",
    )
    file_url: Optional[str] = Field(
        None,
        description="Cloudinary or local URL to the persisted file",
    )
    cloudinary_public_id: Optional[str] = Field(
        None,
        description="Predictable ID used as the Cloudinary asset name",
    )
    size_bytes: int = Field(
        ...,
        ge=0,
        description="Size of the PDF file in bytes",
    )
    total_pages: int = Field(
        0,
        ge=0,
        description="Page count from the parsed PDF",
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(None)

    class Settings:
        name = "exam_files"
        indexes = [
            IndexModel(
                [("file_hash", ASCENDING)],
                name="idx_file_hash_unique",
                unique=True,
            ),
            IndexModel([("paper_id", ASCENDING)], name="idx_paper_id"),
            IndexModel([("cloudinary_public_id", ASCENDING)], name="idx_cloudinary_public_id"),
            IndexModel([("created_at", DESCENDING)], name="idx_created_desc"),
        ]
