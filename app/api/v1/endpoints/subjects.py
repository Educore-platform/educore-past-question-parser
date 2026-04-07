from datetime import datetime, timezone
from typing import Annotated, Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from app.core import cache
from app.models.exam_paper import ExamPaperDocument
from app.models.exam_type import ExamTypeDocument
from app.models.question import QuestionDocument
from app.models.subject import SubjectDocument
from app.schemas.api_response import ApiResponse, api_success
from app.schemas.subject import (
    SubjectCreate,
    SubjectListResponse,
    SubjectOut,
    SubjectUpdate,
    subject_to_out,
)
from app.services.question_service import map_exam_type_ids_to_codes

router = APIRouter(prefix="/subjects", tags=["subjects"])

_INVALID_ID_MSG = "Invalid subject id"
_SUBJECT_NOT_FOUND_MSG = "Subject not found"
_CACHE_STATS = "question:stats"
_CACHE_FILTERS_PATTERN = "question:filters:*"


@router.get(
    "",
    summary="List subjects",
    description="Returns all subjects, optionally filtered by exam type code. Sorted alphabetically by name.",
)
async def list_subjects(
    exam_type: Annotated[Optional[str], Query(alias="examType")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ApiResponse[SubjectListResponse]:
    filters: dict = {}
    if exam_type:
        et_doc = await ExamTypeDocument.find_one(ExamTypeDocument.code == exam_type)
        if et_doc is None:
            raise HTTPException(status_code=404, detail=f"Exam type '{exam_type}' not found")
        filters["exam_type_id"] = et_doc.id

    total = await SubjectDocument.find(filters).count()
    docs = (
        await SubjectDocument.find(filters)
        .sort(+SubjectDocument.name)
        .skip(skip)
        .limit(limit)
        .to_list()
    )

    et_ids = [d.exam_type_id for d in docs if d.exam_type_id]
    et_map = await map_exam_type_ids_to_codes(et_ids)

    return api_success(
        SubjectListResponse(
            items=[subject_to_out(d, exam_types=et_map) for d in docs],
            total=total,
        )
    )


@router.post(
    "",
    status_code=201,
    summary="Create a subject",
    description="Register a new subject. `name` must be unique. Optionally link to an exam type by id.",
)
async def create_subject(body: SubjectCreate) -> ApiResponse[SubjectOut]:
    exam_type_oid: Optional[PydanticObjectId] = None
    if body.exam_type_id:
        try:
            exam_type_oid = PydanticObjectId(body.exam_type_id)
        except (ValueError, TypeError, InvalidId) as e:
            raise HTTPException(status_code=400, detail="Invalid exam_type_id") from e
        et = await ExamTypeDocument.get(exam_type_oid)
        if et is None:
            raise HTTPException(status_code=404, detail="Exam type not found")

    existing = await SubjectDocument.find_one({
        "name": body.name,
        "exam_type_id": exam_type_oid,
    })
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Subject '{body.name}' already exists for this exam type",
        )

    doc = SubjectDocument(
        name=body.name,
        exam_type_id=exam_type_oid,
        aliases=body.aliases,
    )
    await doc.insert()

    et_map = await map_exam_type_ids_to_codes([doc.exam_type_id] if doc.exam_type_id else [])
    await cache.delete(_CACHE_STATS)
    await cache.delete_pattern(_CACHE_FILTERS_PATTERN)
    return api_success(subject_to_out(doc, exam_types=et_map), message="Subject created")


@router.get(
    "/{subject_id}",
    summary="Get one subject",
    responses={404: {"description": "No document with this id"}},
)
async def get_subject(
    subject_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
) -> ApiResponse[SubjectOut]:
    try:
        oid = PydanticObjectId(subject_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await SubjectDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail=_SUBJECT_NOT_FOUND_MSG)

    et_map = await map_exam_type_ids_to_codes([doc.exam_type_id] if doc.exam_type_id else [])
    return api_success(subject_to_out(doc, exam_types=et_map))


@router.put(
    "/{subject_id}",
    summary="Update a subject",
    responses={404: {"description": "No document with this id"}},
)
async def update_subject(
    subject_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
    body: SubjectUpdate,
) -> ApiResponse[SubjectOut]:
    try:
        oid = PydanticObjectId(subject_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await SubjectDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail=_SUBJECT_NOT_FOUND_MSG)

    if body.name is not None and body.name != doc.name:
        new_et_oid = doc.exam_type_id
        if body.exam_type_id is not None:
            try:
                new_et_oid = PydanticObjectId(body.exam_type_id)
            except (ValueError, TypeError, InvalidId) as e:
                raise HTTPException(status_code=400, detail="Invalid exam_type_id") from e
        conflict = await SubjectDocument.find_one({
            "name": body.name,
            "exam_type_id": new_et_oid,
        })
        if conflict and conflict.id != doc.id:
            raise HTTPException(
                status_code=409,
                detail=f"Subject '{body.name}' already exists for this exam type",
            )
        doc.name = body.name

    if body.aliases is not None:
        doc.aliases = body.aliases

    if body.exam_type_id is not None:
        try:
            et_oid = PydanticObjectId(body.exam_type_id)
        except (ValueError, TypeError, InvalidId) as e:
            raise HTTPException(status_code=400, detail="Invalid exam_type_id") from e
        et = await ExamTypeDocument.get(et_oid)
        if et is None:
            raise HTTPException(status_code=404, detail="Exam type not found")
        doc.exam_type_id = et_oid

    doc.updated_at = datetime.now(timezone.utc)
    await doc.save()

    await cache.delete(_CACHE_STATS)
    await cache.delete_pattern(_CACHE_FILTERS_PATTERN)

    et_map = await map_exam_type_ids_to_codes([doc.exam_type_id] if doc.exam_type_id else [])
    return api_success(subject_to_out(doc, exam_types=et_map))


class SubjectReassignBody(BaseModel):
    from_subject_id: str = Field(
        ...,
        description="ObjectId of the subject to migrate away from (may be deleted)",
    )
    to_subject_id: str = Field(
        ...,
        description="ObjectId of the target subject that will own the questions and papers",
    )


@router.post(
    "/reassign",
    summary="Bulk-reassign questions and papers to a different subject",
    description=(
        "Updates every QuestionDocument and ExamPaperDocument that currently references "
        "`from_subject_id` to point at `to_subject_id` instead. "
        "Use this to repair orphaned questions caused by an accidentally deleted subject."
    ),
)
async def reassign_subject(body: SubjectReassignBody) -> ApiResponse[dict]:
    try:
        from_oid = PydanticObjectId(body.from_subject_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail="Invalid from_subject_id") from e

    try:
        to_oid = PydanticObjectId(body.to_subject_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail="Invalid to_subject_id") from e

    if from_oid == to_oid:
        raise HTTPException(status_code=400, detail="from_subject_id and to_subject_id must differ")

    target = await SubjectDocument.get(to_oid)
    if target is None:
        raise HTTPException(status_code=404, detail="Target subject not found")

    q_result = await QuestionDocument.find(
        QuestionDocument.subject_id == from_oid
    ).update({"$set": {"subject_id": to_oid}})

    p_result = await ExamPaperDocument.find(
        ExamPaperDocument.subject_id == from_oid
    ).update({"$set": {"subject_id": to_oid}})

    questions_updated = q_result.modified_count if q_result else 0
    papers_updated = p_result.modified_count if p_result else 0

    await cache.delete(_CACHE_STATS)
    await cache.delete_pattern(_CACHE_FILTERS_PATTERN)

    return api_success(
        {
            "from_subject_id": body.from_subject_id,
            "to_subject_id": body.to_subject_id,
            "to_subject_name": target.name,
            "questions_updated": questions_updated,
            "papers_updated": papers_updated,
        },
        message=f"Reassigned {questions_updated} question(s) and {papers_updated} paper(s) to '{target.name}'",
    )


@router.delete(
    "/{subject_id}",
    summary="Delete a subject",
    description="Deletion is rejected if any exam papers or questions are linked to this subject.",
    responses={
        404: {"description": "No document with this id"},
        409: {"description": "Exam papers still reference this subject"},
    },
)
async def delete_subject(
    subject_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
) -> ApiResponse[dict]:
    try:
        oid = PydanticObjectId(subject_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await SubjectDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail=_SUBJECT_NOT_FOUND_MSG)

    linked_papers = await ExamPaperDocument.find(ExamPaperDocument.subject_id == oid).count()
    if linked_papers:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {linked_papers} exam paper(s) reference this subject",
        )

    linked_questions = await QuestionDocument.find(QuestionDocument.subject_id == oid).count()
    if linked_questions:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {linked_questions} question(s) reference this subject",
        )

    await doc.delete()
    await cache.delete("question:stats")
    await cache.delete_pattern("question:filters:*")
    return api_success({"deleted_id": subject_id})
