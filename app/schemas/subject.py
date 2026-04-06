from datetime import datetime
from typing import Dict, List, Optional

from beanie import PydanticObjectId
from pydantic import BaseModel, Field

from app.models.subject import SubjectDocument


class SubjectCreate(BaseModel):
    name: str = Field(..., description="Canonical subject name, e.g. 'Government'")
    exam_type_id: Optional[str] = Field(None, description="ExamType document id")
    aliases: List[str] = Field(default_factory=list, description="Alternate spellings")


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    exam_type_id: Optional[str] = Field(None, description="ExamType document id")
    aliases: Optional[List[str]] = None


class SubjectOut(BaseModel):
    id: str = Field(..., description="MongoDB document id")
    name: str
    exam_type_id: Optional[str] = None
    exam_type: str = Field(..., alias="examType")
    aliases: List[str]
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class SubjectListResponse(BaseModel):
    items: List[SubjectOut]
    total: int


def subject_to_out(
    doc: SubjectDocument,
    *,
    exam_types: Optional[Dict[PydanticObjectId, str]] = None,
) -> SubjectOut:
    exam_code = ""
    if doc.exam_type_id and exam_types is not None:
        exam_code = exam_types.get(doc.exam_type_id) or ""
    return SubjectOut(
        id=str(doc.id),
        name=doc.name,
        exam_type_id=str(doc.exam_type_id) if doc.exam_type_id else None,
        examType=exam_code,
        aliases=doc.aliases,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
