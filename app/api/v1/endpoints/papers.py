from typing import Annotated, Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Path, Query

from app.models.exam_file import ExamFileDocument
from app.models.exam_paper import ExamPaperDocument
from app.models.question import QuestionDocument
from app.schemas.api_response import ApiResponse, api_success
from app.schemas.paper import ExamPaperListResponse, ExamPaperOut, paper_to_out
from app.services.question_service import (
    build_paper_filters,
    map_exam_type_ids_to_codes,
    map_paper_ids_to_exam_files,
    map_subject_ids_to_names,
)

router = APIRouter(prefix="/papers", tags=["papers"])

_INVALID_ID_MSG = "Invalid paper id"
_MAX_LIMIT = 200


@router.get(
    "",
    response_model=ApiResponse[ExamPaperListResponse],
    summary="List exam papers",
    description=(
        "Returns all exam paper imports with linked file metadata. "
        "Filter by subject name, exam type code, year, or subject id. "
        "Sorted by most recently imported first."
    ),
)
async def list_papers(
    subject: Annotated[Optional[str], Query()] = None,
    exam_type: Annotated[Optional[str], Query(alias="examType")] = None,
    year: Annotated[Optional[int], Query(description="Filter by year (integer, e.g. 2019)")] = None,
    subject_id: Annotated[Optional[str], Query()] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = 50,
) -> ApiResponse[ExamPaperListResponse]:
    try:
        filters = await build_paper_filters(
            subject=subject,
            year=year,
            exam_type=exam_type,
            subject_id=subject_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    total = await ExamPaperDocument.find(filters).count()
    docs = (
        await ExamPaperDocument.find(filters)
        .sort(-ExamPaperDocument.created_at)
        .skip(skip)
        .limit(limit)
        .to_list()
    )

    subj_m = await map_subject_ids_to_names([p.subject_id for p in docs])
    et_m = await map_exam_type_ids_to_codes([p.exam_type_id for p in docs])
    file_by_paper = await map_paper_ids_to_exam_files([p.id for p in docs])

    items = [
        paper_to_out(p, subjects=subj_m, exam_types=et_m, exam_file=file_by_paper.get(p.id))
        for p in docs
    ]
    return api_success(
        ExamPaperListResponse(items=items, total=total, skip=skip, limit=limit)
    )


@router.get(
    "/{paper_id}",
    response_model=ApiResponse[ExamPaperOut],
    summary="Get one exam paper",
    responses={404: {"description": "No document with this id"}},
)
async def get_paper(
    paper_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
) -> ApiResponse[ExamPaperOut]:
    try:
        oid = PydanticObjectId(paper_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await ExamPaperDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Exam paper not found")

    subj_m = await map_subject_ids_to_names([doc.subject_id])
    et_m = await map_exam_type_ids_to_codes([doc.exam_type_id])
    file_map = await map_paper_ids_to_exam_files([doc.id])

    return api_success(
        paper_to_out(doc, subjects=subj_m, exam_types=et_m, exam_file=file_map.get(doc.id))
    )


@router.delete(
    "/{paper_id}",
    response_model=ApiResponse[dict],
    summary="Delete an exam paper",
    description=(
        "Cascade-deletes all questions and the linked exam file record for this paper, "
        "then deletes the paper itself. The PDF file on disk is not removed."
    ),
    responses={404: {"description": "No document with this id"}},
)
async def delete_paper(
    paper_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
) -> ApiResponse[dict]:
    try:
        oid = PydanticObjectId(paper_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await ExamPaperDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Exam paper not found")

    deleted_questions = await QuestionDocument.find(
        QuestionDocument.paper_id == oid
    ).delete()
    deleted_file = await ExamFileDocument.find(
        ExamFileDocument.paper_id == oid
    ).delete()

    await doc.delete()

    return api_success(
        {
            "deleted_id": paper_id,
            "deleted_questions": deleted_questions.deleted_count if deleted_questions else 0,
            "deleted_exam_files": deleted_file.deleted_count if deleted_file else 0,
        }
    )
