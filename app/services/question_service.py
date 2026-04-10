import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from beanie import PydanticObjectId

from app.core import cache
from app.models.exam_file import ExamFileDocument
from app.models.exam_paper import ExamPaperDocument
from app.models.exam_type import ExamTypeDocument
from app.models.question import QuestionDocument
from app.models.subject import SubjectDocument


# ---------------------------------------------------------------------------
# Exam type helpers
# ---------------------------------------------------------------------------


def _normalize_exam_type_code(code: str) -> str:
    """Upper-case and strip an exam type code (e.g. jamb -> JAMB)."""
    t = (code or "").strip().upper()
    return t or "UNKNOWN"


async def get_or_create_exam_type(raw_code: str) -> ExamTypeDocument:
    """Return existing ExamTypeDocument by code (case-insensitive) or insert one."""
    code = _normalize_exam_type_code(raw_code)
    cache_key = f"exam_type:code:{code}"

    cached = await cache.get_json(cache_key)
    if cached is not None:
        doc = ExamTypeDocument.model_validate(cached)
        return doc

    doc = await ExamTypeDocument.find_one(
        {"code": {"$regex": f"^{re.escape(code)}$", "$options": "i"}}
    )
    if doc is None:
        doc = ExamTypeDocument(code=code, name=code)
        await doc.insert()

    await cache.set_json(cache_key, doc.model_dump(mode="json"), ttl=3600)
    return doc


async def resolve_exam_type_id_by_code(code: str) -> Optional[PydanticObjectId]:
    """Return ExamType id for a code, or None if not in the registry."""
    c = _normalize_exam_type_code(code)
    cache_key = f"exam_type:code:{c}"

    cached = await cache.get_json(cache_key)
    if cached is not None:
        try:
            return PydanticObjectId(str(cached.get("id") or cached.get("_id")))
        except Exception:
            pass

    doc = await ExamTypeDocument.find_one(
        {"code": {"$regex": f"^{re.escape(c)}$", "$options": "i"}}
    )
    if doc is not None:
        await cache.set_json(cache_key, doc.model_dump(mode="json"), ttl=3600)
    return doc.id if doc else None


# ---------------------------------------------------------------------------
# Subject helpers
# ---------------------------------------------------------------------------


def _normalize_subject_name(name: str) -> str:
    """Title-case and strip a subject name for use as the unique key."""
    return (name or "").strip().title() or "Unknown"


async def resolve_subject_id_by_name(name: str) -> Optional[PydanticObjectId]:
    """Return Subject id for a canonical name, or None if not in the registry.

    When multiple subjects share the same name (different exam types) the
    first match is returned. Callers that also filter by exam type will
    naturally scope to the correct document via the exam_type filter.
    """
    canonical = _normalize_subject_name(name)
    cache_key = f"subject:name:{canonical}"

    cached = await cache.get_json(cache_key)
    if cached is not None:
        try:
            return PydanticObjectId(str(cached.get("id") or cached.get("_id")))
        except Exception:
            pass

    doc = await SubjectDocument.find_one(
        {"name": {"$regex": f"^{re.escape(canonical)}$", "$options": "i"}}
    )
    if doc is not None:
        await cache.set_json(cache_key, doc.model_dump(mode="json"), ttl=3600)
    return doc.id if doc else None


async def get_or_create_subject(
    subject_name: str,
    exam_type_doc: ExamTypeDocument,
) -> SubjectDocument:
    """
    Return the existing SubjectDocument for ``subject_name`` scoped to
    ``exam_type_doc`` (case-insensitive), creating one if it does not yet
    exist. The unique key is ``(name, exam_type_id)``.
    """
    canonical = _normalize_subject_name(subject_name)
    cache_key = f"subject:name:{canonical}:{exam_type_doc.id}"

    cached = await cache.get_json(cache_key)
    if cached is not None:
        try:
            doc = SubjectDocument.model_validate(cached)
            return doc
        except Exception:
            pass

    doc = await SubjectDocument.find_one({
        "name": {"$regex": f"^{re.escape(canonical)}$", "$options": "i"},
        "exam_type_id": exam_type_doc.id,
    })
    if doc is None:
        doc = SubjectDocument(
            name=canonical,
            exam_type_id=exam_type_doc.id,
            aliases=[],
        )
        await doc.insert()
        await cache.set_json(cache_key, doc.model_dump(mode="json"), ttl=3600)
    else:
        raw = (subject_name or "").strip()
        if raw and raw != canonical and raw not in doc.aliases:
            doc.aliases.append(raw)
            doc.updated_at = datetime.now(timezone.utc)
            await doc.save()
        await cache.set_json(cache_key, doc.model_dump(mode="json"), ttl=3600)
    return doc


# ---------------------------------------------------------------------------
# Display hydration (IDs → names/codes for API responses)
# ---------------------------------------------------------------------------


async def map_subject_ids_to_names(
    ids: List[Optional[PydanticObjectId]],
) -> Dict[PydanticObjectId, str]:
    cleaned = [i for i in ids if i is not None]
    if not cleaned:
        return {}
    unique: List[PydanticObjectId] = list(dict.fromkeys(cleaned))
    docs = await SubjectDocument.find({"_id": {"$in": unique}}).to_list()
    return {d.id: d.name for d in docs}


async def map_exam_type_ids_to_codes(
    ids: List[Optional[PydanticObjectId]],
) -> Dict[PydanticObjectId, str]:
    cleaned = [i for i in ids if i is not None]
    if not cleaned:
        return {}
    unique: List[PydanticObjectId] = list(dict.fromkeys(cleaned))
    docs = await ExamTypeDocument.find({"_id": {"$in": unique}}).to_list()
    return {d.id: d.code for d in docs}


async def hydrate_question_display_fields(
    docs: List[QuestionDocument],
) -> Tuple[Dict[PydanticObjectId, str], Dict[PydanticObjectId, str], Dict[PydanticObjectId, str]]:
    subj = await map_subject_ids_to_names([d.subject_id for d in docs])
    et = await map_exam_type_ids_to_codes([d.exam_type_id for d in docs])
    pc = await map_paper_ids_to_paper_codes([d.paper_id for d in docs])
    return subj, et, pc


async def map_paper_ids_to_paper_codes(
    paper_ids: List[Optional[PydanticObjectId]],
) -> Dict[PydanticObjectId, str]:
    cleaned = [i for i in paper_ids if i is not None]
    if not cleaned:
        return {}
    unique: List[PydanticObjectId] = list(dict.fromkeys(cleaned))
    docs = await ExamPaperDocument.find({"_id": {"$in": unique}}).to_list()
    return {d.id: (d.paper_code or "") for d in docs}


async def map_paper_ids_to_exam_files(
    paper_ids: List[PydanticObjectId],
) -> Dict[PydanticObjectId, ExamFileDocument]:
    """At most one exam file per paper (current import model is 1:1)."""
    if not paper_ids:
        return {}
    unique: List[PydanticObjectId] = list(dict.fromkeys(paper_ids))
    rows = await ExamFileDocument.find({"paper_id": {"$in": unique}}).to_list()
    return {r.paper_id: r for r in rows}


# ---------------------------------------------------------------------------
# Import / idempotency helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExistingImportSummary:
    """Upload metadata recovered from ``exam_files`` / ``exam_papers`` for idempotent replays."""

    filename: str
    paper_id: str
    paper_code: Optional[str]
    total_questions: int
    years_detected: List[int]
    total_pages: int


async def find_import_summary_by_file_hash(file_hash: str) -> Optional[ExistingImportSummary]:
    """If this PDF was already stored (same SHA-256), return summary via ``exam_files``."""
    cache_key = f"file_hash:{file_hash}"

    cached = await cache.get_json(cache_key)
    if cached is not None:
        return ExistingImportSummary(**cached)

    ef = await ExamFileDocument.find_one(ExamFileDocument.file_hash == file_hash)
    if ef is None:
        return None
    paper = await ExamPaperDocument.get(ef.paper_id)
    if paper is None:
        return None

    summary = ExistingImportSummary(
        filename=ef.filename,
        paper_id=str(paper.id),
        paper_code=paper.paper_code,
        total_questions=paper.total_questions,
        years_detected=list(paper.years_detected),
        total_pages=ef.total_pages,
    )
    await cache.set_json(cache_key, summary.__dict__)
    return summary


# ---------------------------------------------------------------------------
# Persist
# ---------------------------------------------------------------------------


async def persist_parsed_questions(
    questions: List[dict],
    *,
    filename: str,
    file_hash: str,
    source_total_pages: int,
    size_bytes: int,
        file_url: Optional[str] = None,
        cloudinary_public_id: Optional[str] = None,
    paper_code_override: Optional[str] = None,
) -> Tuple[int, Optional[str], Optional[str]]:
    """
    Persist all parsed question dicts from one PDF extract as one group.

    Idempotent on ``file_hash``: if an ``ExamFileDocument`` with the same
    SHA-256 already exists (e.g. from a previous attempt that partially
    succeeded), the function returns the existing paper info without
    re-inserting anything.  This makes job retries safe.

    1. Idempotency guard: check ``ExamFileDocument.file_hash``.
    2. Upserts a SubjectDocument for the detected subject (scoped to exam type).
    3. Creates an ExamPaperDocument (one per PDF).
    4. Creates an ExamFileDocument with identity metadata linked to the paper.
    5. Bulk-inserts QuestionDocuments referencing the paper.

    Returns ``(count_inserted, paper_id_hex, paper_code)``.
    """
    if not questions:
        return 0, None, None

    # Idempotency guard: if this file was already persisted (e.g. the worker
    # crashed after insert but before marking the job done), return existing data.
    existing_file = await ExamFileDocument.find_one(ExamFileDocument.file_hash == file_hash)
    if existing_file is not None:
        paper = await ExamPaperDocument.get(existing_file.paper_id)
        return 0, str(existing_file.paper_id), (paper.paper_code if paper else None)

    raw_subject = questions[0].get("subject") or "Unknown"
    raw_exam_type = questions[0].get("exam") or "JAMB"

    from app.services.paper_code_service import get_next_paper_code as _get_next_code

    exam_type_doc = await get_or_create_exam_type(raw_exam_type)
    subject_doc = await get_or_create_subject(raw_subject, exam_type_doc)
    paper_code = paper_code_override or await _get_next_code(subject_doc.id)

    years_found: List[int] = sorted(
        {int(q["year"]) for q in questions if q.get("year")}
    )

    paper = ExamPaperDocument(
        subject_id=subject_doc.id,
        paper_code=paper_code,
        exam_type_id=exam_type_doc.id,
        years_detected=years_found,
        total_questions=len(questions),
    )
    await paper.insert()

    exam_file = ExamFileDocument(
        paper_id=paper.id,
        filename=filename,
        file_hash=file_hash,
        file_url=file_url,
        cloudinary_public_id=cloudinary_public_id,
        size_bytes=size_bytes,
        total_pages=source_total_pages,
    )
    await exam_file.insert()

    docs: List[QuestionDocument] = []
    for q in questions:
        q_exam = q.get("exam") or raw_exam_type
        q_et = (
            exam_type_doc
            if _normalize_exam_type_code(q_exam) == _normalize_exam_type_code(exam_type_doc.code)
            else await get_or_create_exam_type(q_exam)
        )
        docs.append(
            QuestionDocument(
                paper_id=paper.id,
                subject_id=subject_doc.id,
                exam_type_id=q_et.id,
                year=int(q["year"]) if q.get("year") else None,
                question_number=int(q["question_number"]),
                question=q.get("question") or "",
                question_latex=q.get("question_latex"),
                options=q.get("options") or {},
                options_latex=q.get("options_latex") or {},
                answer=q.get("answer"),
                explanation=q.get("explanation"),
                image_url=q.get("image_url"),
            )
        )

    await QuestionDocument.insert_many(docs)
    return len(docs), str(paper.id), paper_code


# ---------------------------------------------------------------------------
# Filter builders
# ---------------------------------------------------------------------------


async def _apply_subject_filter(
    filters: dict, subject: Optional[str] = None, subject_id: Optional[str] = None
) -> None:
    if subject_id is not None:
        try:
            filters["subject_id"] = PydanticObjectId(subject_id)
        except (ValueError, TypeError) as e:
            raise ValueError("Invalid subject_id") from e
    elif subject is not None:
        sid = await resolve_subject_id_by_name(subject)
        filters["subject_id"] = sid if sid is not None else {"$in": []}


async def _apply_exam_type_filter(filters: dict, exam_type: Optional[str] = None) -> None:
    if exam_type is not None:
        eid = await resolve_exam_type_id_by_code(exam_type)
        filters["exam_type_id"] = eid if eid is not None else {"$in": []}


def _apply_paper_id_filter(filters: dict, paper_id: Optional[str] = None) -> None:
    if paper_id is None:
        return

    try:
        filters["paper_id"] = PydanticObjectId(paper_id)
    except (ValueError, TypeError) as e:
        raise ValueError("Invalid paper_id") from e


async def build_question_filters(
    *,
    year: Optional[int] = None,
    subject: Optional[str] = None,
    exam_type: Optional[str] = None,
    question_number: Optional[int] = None,
    paper_id: Optional[str] = None,
    subject_id: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """Build a MongoDB filter dict for question list queries."""
    filters: dict = {}

    if year is not None:
        filters["year"] = year

    await _apply_subject_filter(filters, subject, subject_id)
    await _apply_exam_type_filter(filters, exam_type)
    _apply_paper_id_filter(filters, paper_id)

    if question_number is not None:
        filters["question_number"] = question_number

    if search:
        filters["$text"] = {"$search": search}

    return filters


async def build_paper_filters(
    *,
    subject: Optional[str] = None,
    year: Optional[int] = None,
    exam_type: Optional[str] = None,
    subject_id: Optional[str] = None,
) -> dict:
    """Build a MongoDB filter dict for exam_papers queries."""
    filters: dict = {}

    await _apply_subject_filter(filters, subject, subject_id)
    await _apply_exam_type_filter(filters, exam_type)

    if year is not None:
        filters["years_detected"] = year

    return filters
