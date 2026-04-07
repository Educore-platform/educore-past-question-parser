"""
Schemas for the async PDF extraction job API.

Clients receive a ``JobEnqueuedItem`` immediately after upload and poll
``GET /api/v1/jobs/{job_id}`` to get a ``JobResponse``.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class JobEnqueuedItem(BaseModel):
    """Lightweight acknowledgement returned immediately after a file is queued."""

    job_id: str
    filename: str
    status: str = Field("queued", description="Always 'queued' at enqueue time")


class JobSubmitResponse(BaseModel):
    """Response body for POST /extract/questions (async mode)."""

    jobs: list[JobEnqueuedItem]
    file_count: int
    total_size_bytes: int


class JobResponse(BaseModel):
    """Full job status returned by GET /api/v1/jobs/{job_id}."""

    job_id: str
    status: str = Field(
        ...,
        description="One of: queued, processing, done, failed",
    )
    original_filename: str
    stored_filename: Optional[str] = None
    file_hash: str
    result: Optional[dict[str, Any]] = Field(
        None,
        description="Populated when status=done; keys match ExtractQuestionsUploadSummary",
    )
    error: Optional[str] = Field(None, description="Populated when status=failed")
    created_at: str
    updated_at: Optional[str] = None
