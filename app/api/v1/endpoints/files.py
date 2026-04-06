from typing import Annotated, Optional

from beanie import PydanticObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Path, Query

from app.models.exam_file import ExamFileDocument
from app.schemas.api_response import ApiResponse, api_success
from app.schemas.file import ExamFileListResponse, ExamFileOut, file_to_out

router = APIRouter(prefix="/files", tags=["files"])

_INVALID_ID_MSG = "Invalid file id"
_MAX_LIMIT = 200


@router.get(
    "",
    response_model=ApiResponse[ExamFileListResponse],
    summary="List exam files",
    description=(
        "Returns stored PDF file records. Optionally filter by the parent exam paper id. "
        "Sorted by most recently created first."
    ),
)
async def list_files(
    paper_id: Annotated[
        Optional[str], Query(description="Filter by parent ExamPaper id")
    ] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = 50,
) -> ApiResponse[ExamFileListResponse]:
    filters: dict = {}
    if paper_id:
        try:
            filters["paper_id"] = PydanticObjectId(paper_id)
        except (ValueError, TypeError, InvalidId) as e:
            raise HTTPException(status_code=400, detail="Invalid paper_id") from e

    total = await ExamFileDocument.find(filters).count()
    docs = (
        await ExamFileDocument.find(filters)
        .sort(-ExamFileDocument.created_at)
        .skip(skip)
        .limit(limit)
        .to_list()
    )
    return api_success(
        ExamFileListResponse(
            items=[file_to_out(d) for d in docs],
            total=total,
            skip=skip,
            limit=limit,
        )
    )


@router.get(
    "/{file_id}",
    response_model=ApiResponse[ExamFileOut],
    summary="Get one exam file",
    responses={404: {"description": "No document with this id"}},
)
async def get_file(
    file_id: Annotated[str, Path(description="MongoDB ObjectId hex string")],
) -> ApiResponse[ExamFileOut]:
    try:
        oid = PydanticObjectId(file_id)
    except (ValueError, TypeError, InvalidId) as e:
        raise HTTPException(status_code=400, detail=_INVALID_ID_MSG) from e

    doc = await ExamFileDocument.get(oid)
    if doc is None:
        raise HTTPException(status_code=404, detail="Exam file not found")
    return api_success(file_to_out(doc))
