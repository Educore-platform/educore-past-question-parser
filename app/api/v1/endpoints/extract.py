"""
PDF extraction endpoint.

POST /api/v1/extract/questions
    Validates uploads, hashes bytes in memory, short-circuits duplicates
    before any disk write, saves new files, creates a ``ProcessingJobDocument``
    per file, enqueues ``run_extraction_job`` as a FastAPI BackgroundTask, and
    returns a list of job IDs immediately.

Clients poll GET /api/v1/jobs/{job_id} for status.  When status is "done"
the job's ``result`` field contains the full extraction summary.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile

from app.models.processing_job import ProcessingJobDocument
from app.schemas.api_response import ApiResponse, api_success
from app.schemas.job import JobEnqueuedItem
from app.schemas.responses import ExtractQuestionsJobSummary
from app.services.file_service import FileService, get_file_service
from app.services.job_service import run_extraction_job
from app.services.question_service import find_import_summary_by_file_hash

router = APIRouter(prefix="/extract", tags=["extract"])

MAX_PDF_FILES = 20
MAX_TOTAL_UPLOAD_BYTES = 50 * 1024 * 1024


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _read_upload(file: UploadFile) -> tuple[Optional[str], bytes, str]:
    data = await file.read()
    file_hash = hashlib.sha256(data).hexdigest()
    return file.filename, data, file_hash


def _validate_multi_pdf_upload(chunks: list[tuple[Optional[str], bytes, str]]) -> int:
    if not chunks:
        raise HTTPException(status_code=400, detail="At least one PDF file is required.")
    if len(chunks) > MAX_PDF_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_PDF_FILES} PDF files allowed.",
        )
    total = 0
    for name, data, _hash in chunks:
        if not name or not name.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Every upload must be a PDF file (.pdf).")
        if not data:
            raise HTTPException(status_code=400, detail=f"Empty file: {name or '(unnamed)'}")
        total += len(data)
    if total > MAX_TOTAL_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Total upload size exceeds 50MB.",
        )
    return total


@router.post(
    "/questions",
    response_model=ApiResponse[ExtractQuestionsJobSummary],
    summary="Upload PDFs and queue extraction jobs",
    description=(
        "Upload one or more PDFs, validate them, and immediately return a list of job IDs. "
        "Each file is processed asynchronously — clients poll "
        "``GET /api/v1/jobs/{job_id}`` for status. "
        "Duplicate files (same SHA-256) are detected **before** any disk write and "
        "returned as ``status=duplicate`` with no new job created. "
        "Up to **20 files** and **50 MB total** per request."
    ),
)
async def extract_questions(
    background_tasks: BackgroundTasks,
    file_service: Annotated[FileService, Depends(get_file_service)],
    files: list[UploadFile] = File(
        ...,
        description="One or more JAMB-style past question PDFs (same field repeated; max 20, 50MB combined).",
    ),
    subject: Optional[str] = Query(
        default=None,
        description="Override automatic subject detection (e.g. 'Biology', 'Mathematics') for every file.",
    ),
    exam_type: Optional[str] = Query(
        default=None,
        alias="examType",
        description="Override automatic exam type detection (e.g. 'JAMB', 'WAEC') for every file.",
    ),
) -> ApiResponse[ExtractQuestionsJobSummary]:
    chunks = await asyncio.gather(*(_read_upload(f) for f in files))
    total_size_bytes = _validate_multi_pdf_upload(chunks)

    # Hash-check all files concurrently before touching disk.
    existing_results = await asyncio.gather(
        *(find_import_summary_by_file_hash(fh) for _, _, fh in chunks)
    )
    existing_map: dict[str, object] = {
        fh: ex
        for (_, _, fh), ex in zip(chunks, existing_results)
        if ex is not None
    }

    # Save only genuinely new files.
    async def _save_one(name: Optional[str], data: bytes) -> dict:
        try:
            # Generate a deterministic ID for Cloudinary that we can link back to our DB
            file_id = str(uuid.uuid4())
            return await asyncio.to_thread(
                file_service.save_pdf_bytes,
                name or "document.pdf",
                data,
                public_id=file_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    new_chunks = [(name, data, fh) for name, data, fh in chunks if fh not in existing_map]
    new_metas = await asyncio.gather(*[_save_one(name, data) for name, data, _ in new_chunks])
    meta_by_hash = {fh: meta for (_, _, fh), meta in zip(new_chunks, new_metas)}

    # Build job documents for new files and enqueue background tasks.
    job_docs: list[ProcessingJobDocument] = []
    for _, _, fh in new_chunks:
        meta = meta_by_hash[fh]
        job = ProcessingJobDocument(
            job_id=str(uuid.uuid4()),
            status="queued",
            original_filename=meta["original_filename"],
            file_url=meta["file_url"],
            cloudinary_public_id=meta.get("cloudinary_public_id"),
            file_hash=fh,
            size_bytes=meta["size_bytes"],
            subject_override=subject,
            exam_type_override=exam_type,
        )
        job_docs.append(job)

    if job_docs:
        await asyncio.gather(*(j.insert() for j in job_docs))
        for j in job_docs:
            background_tasks.add_task(run_extraction_job, j.job_id)

    job_by_hash = {j.file_hash: j for j in job_docs}

    # Assemble the response: one item per uploaded file.
    items: list[JobEnqueuedItem] = []
    for name, _, fh in chunks:
        if fh in existing_map:
            items.append(JobEnqueuedItem(job_id="", filename=name or "", status="duplicate"))
        else:
            j = job_by_hash[fh]
            items.append(JobEnqueuedItem(job_id=j.job_id, filename=name or "", status="queued"))

    return api_success(
        ExtractQuestionsJobSummary(
            jobs=items,
            file_count=len(items),
            total_size_bytes=total_size_bytes,
        )
    )
