"""
Async job status endpoint.

Clients poll ``GET /api/v1/jobs/{job_id}`` after submitting files to
``POST /api/v1/extract/questions``.  When ``status`` is ``"done"`` the
``result`` field contains the full extraction summary.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.processing_job import ProcessingJobDocument
from app.schemas.api_response import ApiResponse, api_success
from app.schemas.job import JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "/{job_id}",
    response_model=ApiResponse[JobResponse],
    summary="Poll an extraction job",
    description=(
        "Returns the current status of a PDF extraction job submitted via "
        "``POST /api/v1/extract/questions``. "
        "Possible status values: ``queued``, ``processing``, ``done``, ``failed``. "
        "When ``status`` is ``done``, the ``result`` field contains the full "
        "extraction summary (pages, years, persisted count, paper_id, etc.)."
    ),
)
async def get_job(job_id: str) -> ApiResponse[JobResponse]:
    job = await ProcessingJobDocument.find_one(
        ProcessingJobDocument.job_id == job_id
    )
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    return api_success(
        JobResponse(
            job_id=job.job_id,
            status=job.status,
            original_filename=job.original_filename,
            stored_filename=job.cloudinary_public_id,
            file_hash=job.file_hash,
            result=job.result,
            error=job.error,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat() if job.updated_at else None,
        )
    )
