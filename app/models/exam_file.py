"""
MongoDB document model for uploaded exam PDF files.

Stored in collection ``exam_files``. One row per source file; ``paper_id``
points at the logical ``ExamPaperDocument`` that owns extracted questions.
File bytes live on disk; this document holds identity, hash, and paths.
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
    Metadata for one stored PDF tied to an exam paper import.

    ``file_hash`` (SHA-256 hex) is unique and used for idempotency lookups.
    """

    paper_id: PydanticObjectId = Field(
        ...,
        description="Reference to ExamPaperDocument._id",
    )
    source_original_filename: str = Field(
        ...,
        description="Client-provided filename at upload time",
    )
    stored_filename: str = Field(
        ...,
        description="Unique filename on disk under the upload directory",
    )
    relative_path: str = Field(
        ...,
        description="Path relative to project root (POSIX-style)",
    )
    file_hash: str = Field(
        ...,
        description="Lowercase hex SHA-256 of the PDF bytes; idempotency key",
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
    content_type: str = Field(
        "application/pdf",
        description="MIME type of the stored object",
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
            IndexModel([("created_at", DESCENDING)], name="idx_created_desc"),
        ]
