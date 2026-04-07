import asyncio
import hashlib
from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from app.core import cache
from app.core.events import file_processed
from app.extraction.core.pipeline import run_pipeline
from app.schemas.api_response import ApiResponse, api_success
from app.schemas.responses import ExtractQuestionsMultiUploadSummary, ExtractQuestionsUploadSummary
from app.services.file_service import FileService, get_file_service
from app.services.question_service import find_import_summary_by_file_hash, persist_parsed_questions

router = APIRouter(prefix="/extract", tags=["extract"])

MAX_PDF_FILES = 20
MAX_TOTAL_UPLOAD_BYTES = 50 * 1024 * 1024


async def _read_upload(file: UploadFile) -> tuple[Optional[str], bytes]:
    data = await file.read()
    return file.filename, data


def _validate_multi_pdf_upload(chunks: list[tuple[Optional[str], bytes]]) -> int:
    if not chunks:
        raise HTTPException(status_code=400, detail="At least one PDF file is required.")
    if len(chunks) > MAX_PDF_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_PDF_FILES} PDF files allowed.",
        )
    total = 0
    for name, data in chunks:
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


async def _process_saved_pdf(
    meta: dict,
    subject: Optional[str],
    exam_type: Optional[str],
) -> ExtractQuestionsUploadSummary:
    path = Path(meta["absolute_path"])

    # Compute the hash first so we can check for a duplicate before the
    # expensive pipeline run.
    file_bytes = await asyncio.to_thread(path.read_bytes)
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    existing = await find_import_summary_by_file_hash(file_hash)
    if existing is not None:
        return ExtractQuestionsUploadSummary(
            filename=meta["original_filename"],
            stored_filename=meta["stored_filename"],
            total_pages=existing.total_pages,
            years_detected=existing.years_detected,
            total_questions=existing.total_questions,
            persisted_count=0,
            paper_id=existing.paper_id,
            paper_code=existing.paper_code,
            subject_name=existing.filename,
        )

    result = await asyncio.to_thread(
        run_pipeline,
        path,
        subject_override=subject,
        exam_type_override=exam_type,
    )
    years_found = sorted({int(q["year"]) for q in result.questions if q["year"]})

    persisted, paper_id_str, paper_code_val = await persist_parsed_questions(
        result.questions,
        filename=meta["original_filename"],
        file_hash=file_hash,
        source_total_pages=result.total_pages,
        size_bytes=meta["size_bytes"],
    )
    file_processed.send("extract_questions", path=str(path))

    # Invalidate aggregate caches that are now stale after new questions were
    # inserted.  Use delete_pattern for filters because the key includes the
    # subject scope which we may not know exactly.
    await cache.delete("question:stats")
    await cache.delete_pattern("question:filters:*")

    subject_name = (result.questions[0].get("subject") if result.questions else None) or "Unknown"

    return ExtractQuestionsUploadSummary(
        filename=meta["original_filename"],
        stored_filename=meta["stored_filename"],
        total_pages=result.total_pages,
        years_detected=years_found,
        total_questions=len(result.questions),
        persisted_count=persisted,
        paper_id=paper_id_str,
        paper_code=paper_code_val,
        subject_name=subject_name,
    )


@router.post(
    "/questions",
    response_model=ApiResponse[ExtractQuestionsMultiUploadSummary],
    summary="Upload and extract questions from PDFs",
    description=(
        "Upload one or more PDFs (persisted on disk), parse JAMB-style MCQs, and **persist each question "
        "to MongoDB**. One `ExamPaperDocument` and one `ExamFileDocument` are created per source file; "
        "questions reference the paper via `paper_id`. "
        "Up to **20 files** and **50MB total** per request. Files are read, saved, and parsed **in parallel** "
        "where safe. Fetch stored questions with `GET /api/v1/questions` (e.g. `?paper_id=` or `?subject_id=`). "
        "Diagram images are saved under `data/images/` and served at `/images/<filename>`."
    ),
)
async def extract_questions(
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
):
    chunks = await asyncio.gather(*(_read_upload(f) for f in files))
    total_size_bytes = _validate_multi_pdf_upload(chunks)

    async def _save_one(item: tuple[Optional[str], bytes]) -> dict:
        name, data = item
        try:
            return await asyncio.to_thread(
                file_service.save_pdf_bytes,
                name or "document.pdf",
                data,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    metas = await asyncio.gather(*[_save_one(c) for c in chunks])

    summaries = await asyncio.gather(*(_process_saved_pdf(m, subject, exam_type) for m in metas))

    return api_success(
        ExtractQuestionsMultiUploadSummary(
            results=list(summaries),
            file_count=len(summaries),
            total_size_bytes=total_size_bytes,
        ),
    )
