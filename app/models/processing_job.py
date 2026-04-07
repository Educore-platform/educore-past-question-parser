"""
MongoDB document model for async PDF extraction jobs.

Stored in collection ``processing_jobs``. One document per uploaded file.
The ``job_id`` (UUID) is the external identifier returned to clients; they
poll ``GET /api/v1/jobs/{job_id}`` to check progress.

Lifecycle: queued → processing → done | failed
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProcessingJobDocument(Document):
    """
    Tracks the status of one PDF extraction job.

    ``job_id`` is a UUID string used as the external key.
    ``file_hash`` is the SHA-256 hex of the uploaded PDF — the idempotency key.
    ``result`` is populated on success with a dict matching ``ExtractQuestionsUploadSummary``.
    ``error`` is populated on failure with the exception message.
    """

    job_id: str = Field(..., description="UUID string; external identifier for polling")
    status: str = Field(
        "queued",
        description="One of: queued, processing, done, failed",
    )
    original_filename: str = Field(..., description="Client-provided filename")
    stored_filename: Optional[str] = Field(None, description="Server-side filename under data/uploads/")
    file_path: Optional[str] = Field(None, description="Absolute path on disk (set after save)")
    file_hash: str = Field(..., description="SHA-256 hex of the PDF bytes; idempotency key")
    size_bytes: int = Field(0, ge=0, description="PDF size in bytes")
    subject_override: Optional[str] = Field(None)
    exam_type_override: Optional[str] = Field(None)
    result: Optional[dict[str, Any]] = Field(
        None,
        description="Summary dict when status=done (matches ExtractQuestionsUploadSummary)",
    )
    error: Optional[str] = Field(None, description="Exception message when status=failed")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: Optional[datetime] = Field(None)

    class Settings:
        name = "processing_jobs"
        indexes = [
            IndexModel(
                [("job_id", ASCENDING)],
                name="idx_job_id_unique",
                unique=True,
            ),
            IndexModel([("file_hash", ASCENDING)], name="idx_job_file_hash"),
            IndexModel([("status", ASCENDING)], name="idx_job_status"),
            IndexModel([("created_at", DESCENDING)], name="idx_job_created_desc"),
        ]
