"""
Async extraction job worker.

``run_extraction_job`` is fired as a FastAPI ``BackgroundTask`` immediately
after the HTTP response is sent.  It:

1. Marks the job as ``processing``.
2. Runs the extraction pipeline in a thread (CPU-bound).
3. Persists the results to MongoDB (idempotent on ``file_hash``).
4. Emits ``file_processed`` to clean up the upload from disk.
5. Invalidates stale question caches.
6. Marks the job ``done`` (or ``failed`` on any exception).

The job document's ``result`` field is populated on success with a dict that
matches the ``ExtractQuestionsUploadSummary`` schema so the polling endpoint
can return a complete summary.
"""

import asyncio
import logging
import os
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiofiles
import httpx

from app.core import cache
from app.extraction.core.pipeline import run_pipeline
from app.models.processing_job import ProcessingJobDocument
from app.services.question_service import persist_parsed_questions

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def run_extraction_job(job_id: str) -> None:
    """
    Background worker that processes one PDF extraction job end-to-end.

    Called by FastAPI ``BackgroundTasks`` after the upload response is sent.
    All errors are caught and recorded on the job document so the polling
    endpoint always returns a stable response.
    """
    job = await ProcessingJobDocument.find_one(ProcessingJobDocument.job_id == job_id)
    if job is None:
        logger.error("job_worker | job not found | job_id=%s", job_id)
        return

    job.status = "processing"
    job.updated_at = _utcnow()
    await job.save()
    logger.info("job_worker | started | job_id=%s file=%s", job_id, job.original_filename)

    temp_path: Optional[Path] = None
    try:
        # Remote URL, download to temp file
        logger.info("job_worker | downloading | url=%s", job.file_url)

        # Use a stable temp path but write to it asynchronously
        fd, path_str = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)  # Close the sync file descriptor
        temp_path = Path(path_str)

        async with httpx.AsyncClient() as client:
            async with client.stream("GET", job.file_url) as response:
                response.raise_for_status()
                async with aiofiles.open(temp_path, mode="wb") as f:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)

        pdf_path = temp_path

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found at {pdf_path}")

        result = await asyncio.to_thread(
            run_pipeline,
            pdf_path,
            subject_override=job.subject_override,
            exam_type_override=job.exam_type_override,
        )

        years_found = sorted({int(q["year"]) for q in result.questions if q.get("year")})

        persisted, paper_id_str, paper_code_val = await persist_parsed_questions(
            result.questions,
            filename=job.original_filename,
            file_hash=job.file_hash,
            source_total_pages=result.total_pages,
            size_bytes=job.size_bytes,
            file_url=job.file_url,
            cloudinary_public_id=job.cloudinary_public_id,
        )

        # Cleanup: Delete the temp file.
        if temp_path and temp_path.exists():
            os.unlink(temp_path)
            logger.info("job_worker | temp file deleted | path=%s", temp_path)

        await cache.delete("question:stats")
        await cache.delete_pattern("question:filters:*")

        subject_name = (
            result.questions[0].get("subject") if result.questions else None
        ) or "Unknown"

        job.status = "done"
        job.result = {
            "filename": job.original_filename,
            "total_pages": result.total_pages,
            "years_detected": years_found,
            "total_questions": len(result.questions),
            "persisted_count": persisted,
            "paper_id": paper_id_str,
            "paper_code": paper_code_val,
            "subject_name": subject_name,
            "file_url": job.file_url,
        }
        job.updated_at = _utcnow()
        await job.save()

        logger.info(
            "job_worker | done | job_id=%s persisted=%d paper_id=%s",
            job_id,
            persisted,
            paper_id_str,
        )

    except Exception:
        if temp_path and temp_path.exists():
            os.unlink(temp_path)
        error_detail = traceback.format_exc()
        logger.error(
            "job_worker | failed | job_id=%s\n%s",
            job_id,
            error_detail,
        )
        try:
            job.status = "failed"
            job.error = error_detail
            job.updated_at = _utcnow()
            await job.save()
        except Exception:
            logger.error(
                "job_worker | could not persist failure | job_id=%s", job_id
            )
