from typing import Annotated, Dict, List, Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Path, Query

from app.core import cache
from app.models.exam_paper import ExamPaperDocument
from app.models.exam_type import ExamTypeDocument
from app.models.question import QuestionDocument
from app.models.subject import SubjectDocument
from app.schemas.api_response import ApiResponse, api_success
from app.schemas.question import (
    QuestionListResponse,
    QuestionOut,
    QuestionSummaryListResponse,
    QuestionUpdate,
    question_to_out,
    question_to_summary_out,
)
from app.schemas.responses import (
    DistinctValuesResponse,
    QuestionStatsResponse,
)
from app.services.question_service import (
    build_paper_filters,
    build_question_filters,
    get_or_create_exam_type,
    hydrate_question_display_fields,
    map_exam_type_ids_to_codes,
    map_subject_ids_to_names,
)

router = APIRouter(prefix="/questions", tags=["questions"])

_MAX_LIMIT = 200
_INVALID_ID_MSG = "Invalid question id"


@router.get(
    "",
    response_model=ApiResponse[QuestionListResponse],
    summary="List questions with filters",
    description=(
        "Filter by exam metadata, source paper, or substring search on the question text. "
        "Results are paginated and sorted by subject / year / question_number."
    ),
)
async def list_questions(
    year: Annotated[Optional[int], Query(description="Exact year as an integer, e.g. 2010")] = None,
    subject: Annotated[Optional[str], Query()] = None,
    exam_type: Annotated[Optional[str], Query(alias="examType")] = None,
    question_number: Annotated[
        Optional[int], Query(ge=1, description="Question number within the paper")
    ] = None,
    paper_id: Annotated[
        Optional[str], Query(description="ExamPaper id shared by all questions from one PDF")
    ] = None,
    subject_id: Annotated[
        Optional[str], Query(description="Subject id to filter by subject")
    ] = None,
    search: Annotated[
        Optional[str], Query(description="Full-text search on question stem")
    ] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = 50,
) -> ApiResponse[QuestionListResponse]:
    try:
        filters = await build_question_filters(
            year=year,
            subject=subject,
            exam_type=exam_type,
            question_number=question_number,
            paper_id=paper_id,
            subject_id=subject_id,
            search=search,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    total = await QuestionDocument.find(filters).count()
    docs = (
        await QuestionDocument.find(filters)
        .sort(
            +QuestionDocument.subject_id,
            +QuestionDocument.year,
            +QuestionDocument.exam_type_id,
            +QuestionDocument.question_number,
        )
        .skip(skip)
        .limit(limit)
        .to_list()
    )
    subj_m, et_m, pc_m = await hydrate_question_display_fields(docs)
    return api_success(
        QuestionListResponse(
            items=[question_to_out(d, subjects=subj_m, exam_types=et_m, paper_codes=pc_m) for d in docs],
            total=total,
            skip=skip,
            limit=limit,
        ),
    )


@router.get(
    "/summary",
    response_model=ApiResponse[QuestionSummaryListResponse],
    summary="List question metadata only",
    description=(
        "Same filters and pagination as the full list, but each row omits the stem, options, "
        "LaTeX, answer text, and explanation. Use `GET /questions/{question_id}` for the full document."
    ),
)
async def list_questions_summary(
    year: Annotated[Optional[int], Query(description="Exact year as an integer, e.g. 2010")] = None,
    subject: Annotated[Optional[str], Query()] = None,
    exam_type: Annotated[Optional[str], Query(alias="examType")] = None,
    question_number: Annotated[
        Optional[int], Query(ge=1, description="Question number within the paper")
    ] = None,
    paper_id: Annotated[
        Optional[str], Query(description="ExamPaper id shared by all questions from one PDF")
    ] = None,
    subject_id: Annotated[
        Optional[str], Query(description="Subject id to filter by subject")
    ] = None,
    search: Annotated[
        Optional[str], Query(description="Full-text search on question stem")
    ] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = 50,
) -> ApiResponse[QuestionSummaryListResponse]:
    try:
        filters = await build_question_filters(
            year=year,
            subject=subject,
            exam_type=exam_type,
            question_number=question_number,
            paper_id=paper_id,
            subject_id=subject_id,
            search=search,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    total = await QuestionDocument.find(filters).count()
    docs = (
        await QuestionDocument.find(filters)
        .sort(
            +QuestionDocument.subject_id,
            +QuestionDocument.year,
            +QuestionDocument.exam_type_id,
            +QuestionDocument.question_number,
        )
        .skip(skip)
        .limit(limit)
        .to_list()
    )
    subj_m, et_m, pc_m = await hydrate_question_display_fields(docs)
    return api_success(
        QuestionSummaryListResponse(
            items=[question_to_summary_out(d, subjects=subj_m, exam_types=et_m, paper_codes=pc_m) for d in docs],
            total=total,
            skip=skip,
            limit=limit,
        ),
    )


@router.get(
    "/filters",
    response_model=ApiResponse[DistinctValuesResponse],
    summary="Available filter values",
    description=(
        "Returns distinct subjects, exam types, and years available for filtering questions. "
        "- No params: all distinct years_detected across every paper. "
        "- `subject` only: all distinct years_detected for papers belonging to that subject. "
        "- `paper_id`: distinct years_detected for that specific paper. "
        "- `subject` + `paper_id`: years_detected for that paper (paper_id takes precedence for years)."
    ),
)
async def get_filter_values(
    subject: Annotated[Optional[str], Query()] = None,
    paper_id: Annotated[
        Optional[str], Query(description="Scope years to a specific ExamPaper document id")
    ] = None,
) -> ApiResponse[DistinctValuesResponse]:
    cache_key = f"question:filters:{subject or '__all__'}:{paper_id or '__all__'}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return api_success(DistinctValuesResponse(**cached))

    subjects: List[str] = sorted(
        [doc.name for doc in await SubjectDocument.find_all().to_list()],
        key=str.casefold,
    )

    exam_types_list: List[str] = sorted(
        [d.code for d in await ExamTypeDocument.find_all().to_list()],
        key=str.casefold,
    )

    if paper_id is not None:
        # Years for one specific paper
        try:
            oid = PydanticObjectId(paper_id)
        except (ValueError, TypeError, InvalidId) as e:
            raise HTTPException(status_code=400, detail="Invalid paper_id") from e
        paper_doc = await ExamPaperDocument.get(oid)
        years: List[int] = sorted(
            [v for v in (paper_doc.years_detected if paper_doc else []) if v],
            reverse=True,
        )
    elif subject is not None:
        # Years for all papers belonging to this subject
        paper_filters = await build_paper_filters(subject=subject)
        years = sorted(
            [v for v in await ExamPaperDocument.distinct("years_detected", paper_filters) if v],
            reverse=True,
        )
    else:
        # All distinct years across every paper
        years = sorted(
            [v for v in await ExamPaperDocument.distinct("years_detected") if v],
            reverse=True,
        )

    result = DistinctValuesResponse(subjects=subjects, exam_types=exam_types_list, years=years)
    await cache.set_json(cache_key, result.model_dump(), ttl=600)
    return api_success(result)


@router.get(
    "/stats",
    summary="Aggregate question counts",
    description="Total question count plus per-subject, per-exam-type, and per-year breakdowns.",
)
async def get_question_stats() -> ApiResponse[QuestionStatsResponse]:
    cached = await cache.get_json("question:stats")
    if cached is not None:
        return api_success(QuestionStatsResponse(**cached))

    total = await QuestionDocument.count()

    subject_pipeline = [
        {"$group": {"_id": "$subject_id", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    exam_type_pipeline = [
        {"$group": {"_id": "$exam_type_id", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    year_pipeline = [
        {"$group": {"_id": "$year", "count": {"$sum": 1}}},
        {"$sort": {"_id": -1}},
    ]

    subject_results = await QuestionDocument.aggregate(subject_pipeline).to_list()
    exam_type_results = await QuestionDocument.aggregate(exam_type_pipeline).to_list()
    year_results = await QuestionDocument.aggregate(year_pipeline).to_list()

    subj_ids: List[PydanticObjectId] = []
    for row in subject_results:
        raw = row.get("_id")
        if raw is not None:
            try:
                subj_ids.append(PydanticObjectId(str(raw)))
            except (ValueError, TypeError, InvalidId):
                pass
    et_ids: List[PydanticObjectId] = []
    for row in exam_type_results:
        raw = row.get("_id")
        if raw is not None:
            try:
                et_ids.append(PydanticObjectId(str(raw)))
            except (ValueError, TypeError, InvalidId):
                pass
    subj_map = await map_subject_ids_to_names(subj_ids)
    et_map = await map_exam_type_ids_to_codes(et_ids)

    by_subject: Dict[str, int] = {}
    for row in subject_results:
        oid = row.get("_id")
        if oid is None:
            continue
        try:
            pid = PydanticObjectId(str(oid))
            label = subj_map.get(pid) or f"[Deleted Subject: {str(pid)[:8]}]"
        except (ValueError, TypeError, InvalidId):
            label = f"[Unknown: {str(oid)[:8]}]"
        by_subject[label] = row["count"]

    by_exam_type: Dict[str, int] = {}
    for row in exam_type_results:
        oid = row.get("_id")
        if oid is None:
            continue
        try:
            pid = PydanticObjectId(str(oid))
            label = et_map.get(pid) or f"[Deleted Exam Type: {str(pid)[:8]}]"
        except (ValueError, TypeError, InvalidId):
            label = f"[Unknown: {str(oid)[:8]}]"
        by_exam_type[label] = row["count"]
    by_year: Dict[str, int] = {
        str(row["_id"]): row["count"] for row in year_results if row.get("_id")
    }

    result = QuestionStatsResponse(
        total=total,
        by_subject=by_subject,
        by_exam_type=by_exam_type,
        by_year=by_year,
    )
    await cache.set_json("question:stats", result.model_dump(), ttl=300)
    return api_success(result)


@router.get(
    "/{question_id}",
    response_model=ApiResponse[QuestionOut],
    summary="Get one question by id",
    responses={404: {"description": "No document with this id"}},
)
async def get_question(
    question_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
) -> ApiResponse[QuestionOut]:
    try:
        oid = PydanticObjectId(question_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    cache_key = f"question:{question_id}"
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return api_success(QuestionOut(**cached))

    doc = await QuestionDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Question not found")
    sm, em, pm = await hydrate_question_display_fields([doc])
    out = question_to_out(doc, subjects=sm, exam_types=em, paper_codes=pm)
    await cache.set_json(cache_key, out.model_dump(mode="json"), ttl=600)
    return api_success(out)


@router.put(
    "/{question_id}",
    response_model=ApiResponse[QuestionOut],
    summary="Update one question",
    responses={404: {"description": "No document with this id"}},
)
async def update_question(
    question_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
    update_data: QuestionUpdate,
) -> ApiResponse[QuestionOut]:
    from datetime import datetime, timezone

    try:
        oid = PydanticObjectId(question_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await QuestionDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Question not found")

    update_dict = update_data.model_dump(exclude_unset=True, by_alias=False)
    if "exam_type_id" in update_dict:
        raw_eid = update_dict.pop("exam_type_id")
        if raw_eid:
            try:
                eoid = PydanticObjectId(raw_eid)
            except (ValueError, TypeError, InvalidId) as e:
                raise HTTPException(status_code=400, detail="Invalid exam_type_id") from e
            et = await ExamTypeDocument.get(eoid)
            if et is None:
                raise HTTPException(status_code=400, detail="Unknown exam_type_id")
            doc.exam_type_id = et.id
    if "exam_type" in update_dict:
        code = update_dict.pop("exam_type")
        if code is not None:
            et = await get_or_create_exam_type(code)
            doc.exam_type_id = et.id
    if "subject_id" in update_dict:
        raw_sid = update_dict.pop("subject_id")
        if raw_sid:
            try:
                soid = PydanticObjectId(raw_sid)
            except (ValueError, TypeError, InvalidId) as e:
                raise HTTPException(status_code=400, detail="Invalid subject_id") from e
            sub = await SubjectDocument.get(soid)
            if sub is None:
                raise HTTPException(status_code=400, detail="Unknown subject_id")
            doc.subject_id = sub.id
    for k, v in update_dict.items():
        setattr(doc, k, v)
    doc.updated_at = datetime.now(timezone.utc)

    await doc.save()
    await cache.delete(f"question:{question_id}", "question:stats")
    sm, em, pm = await hydrate_question_display_fields([doc])
    out = question_to_out(doc, subjects=sm, exam_types=em, paper_codes=pm)
    await cache.set_json(f"question:{question_id}", out.model_dump(mode="json"), ttl=600)
    return api_success(out)


@router.delete(
    "/{question_id}",
    response_model=ApiResponse[dict],
    summary="Delete one question",
    responses={404: {"description": "No document with this id"}},
)
async def delete_question(
    question_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
) -> ApiResponse[dict]:
    try:
        oid = PydanticObjectId(question_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await QuestionDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Question not found")

    paper_id = doc.paper_id
    await doc.delete()

    if paper_id is not None:
        paper = await ExamPaperDocument.get(paper_id)
        if paper is not None and paper.total_questions > 0:
            from datetime import datetime, timezone
            paper.total_questions = max(0, paper.total_questions - 1)
            paper.updated_at = datetime.now(timezone.utc)
            await paper.save()

    await cache.delete(f"question:{question_id}", "question:stats")
    return api_success({"message": "Question deleted successfully"})
