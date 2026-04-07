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

from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path

from app.core import cache
from app.core.events import file_processed
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

    try:
        pdf_path = Path(job.file_path)

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
        )

        file_processed.send("job_worker", path=str(pdf_path))

        await cache.delete("question:stats")
        await cache.delete_pattern("question:filters:*")

        subject_name = (
            result.questions[0].get("subject") if result.questions else None
        ) or "Unknown"

        job.status = "done"
        job.result = {
            "filename": job.original_filename,
            "stored_filename": job.stored_filename,
            "total_pages": result.total_pages,
            "years_detected": years_found,
            "total_questions": len(result.questions),
            "persisted_count": persisted,
            "paper_id": paper_id_str,
            "paper_code": paper_code_val,
            "subject_name": subject_name,
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
