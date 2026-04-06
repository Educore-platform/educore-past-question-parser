from datetime import datetime, timezone
from typing import Annotated

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Path, Query

from app.models.exam_type import ExamTypeDocument
from app.models.subject import SubjectDocument
from app.schemas.api_response import ApiResponse, api_success
from app.schemas.exam_type import (
    ExamTypeCreate,
    ExamTypeListResponse,
    ExamTypeOut,
    ExamTypeUpdate,
    exam_type_to_out,
)

router = APIRouter(prefix="/exam-types", tags=["exam-types"])

_INVALID_ID_MSG = "Invalid exam type id"


@router.get(
    "",
    response_model=ApiResponse[ExamTypeListResponse],
    summary="List exam types",
    description="Returns all registered exam types (e.g. JAMB, WAEC), sorted by code.",
)
async def list_exam_types(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ApiResponse[ExamTypeListResponse]:
    total = await ExamTypeDocument.count()
    docs = (
        await ExamTypeDocument.find_all()
        .sort(+ExamTypeDocument.code)
        .skip(skip)
        .limit(limit)
        .to_list()
    )
    return api_success(
        ExamTypeListResponse(items=[exam_type_to_out(d) for d in docs], total=total)
    )


@router.post(
    "",
    response_model=ApiResponse[ExamTypeOut],
    status_code=201,
    summary="Create an exam type",
    description="Register a new exam type. `code` must be unique (case-sensitive).",
)
async def create_exam_type(body: ExamTypeCreate) -> ApiResponse[ExamTypeOut]:
    existing = await ExamTypeDocument.find_one(ExamTypeDocument.code == body.code)
    if existing:
        raise HTTPException(status_code=409, detail=f"Exam type '{body.code}' already exists")
    doc = ExamTypeDocument(code=body.code)
    await doc.insert()
    return api_success(exam_type_to_out(doc), message="Exam type created")


@router.get(
    "/{exam_type_id}",
    response_model=ApiResponse[ExamTypeOut],
    summary="Get one exam type",
    responses={404: {"description": "No document with this id"}},
)
async def get_exam_type(
    exam_type_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
) -> ApiResponse[ExamTypeOut]:
    try:
        oid = PydanticObjectId(exam_type_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await ExamTypeDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Exam type not found")
    return api_success(exam_type_to_out(doc))


@router.put(
    "/{exam_type_id}",
    response_model=ApiResponse[ExamTypeOut],
    summary="Update an exam type",
    responses={404: {"description": "No document with this id"}},
)
async def update_exam_type(
    exam_type_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
    body: ExamTypeUpdate,
) -> ApiResponse[ExamTypeOut]:
    try:
        oid = PydanticObjectId(exam_type_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await ExamTypeDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Exam type not found")

    if body.code is not None and body.code != doc.code:
        conflict = await ExamTypeDocument.find_one(ExamTypeDocument.code == body.code)
        if conflict:
            raise HTTPException(
                status_code=409, detail=f"Exam type '{body.code}' already exists"
            )
        doc.code = body.code

    doc.updated_at = datetime.now(timezone.utc)
    await doc.save()
    return api_success(exam_type_to_out(doc))


@router.delete(
    "/{exam_type_id}",
    response_model=ApiResponse[dict],
    summary="Delete an exam type",
    description="Deletion is rejected if any subjects are linked to this exam type.",
    responses={
        404: {"description": "No document with this id"},
        409: {"description": "Subjects still reference this exam type"},
    },
)
async def delete_exam_type(
    exam_type_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
) -> ApiResponse[dict]:
    try:
        oid = PydanticObjectId(exam_type_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await ExamTypeDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Exam type not found")

    linked = await SubjectDocument.find(SubjectDocument.exam_type_id == oid).count()
    if linked:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {linked} subject(s) reference this exam type",
        )

    await doc.delete()
    return api_success({"deleted_id": exam_type_id})
