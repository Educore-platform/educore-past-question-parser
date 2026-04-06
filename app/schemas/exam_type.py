from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.exam_type import ExamTypeDocument


class ExamTypeCreate(BaseModel):
    code: str = Field(..., description="Unique short code, e.g. 'JAMB', 'WAEC'")


class ExamTypeUpdate(BaseModel):
    code: Optional[str] = Field(None, description="New unique short code")


class ExamTypeOut(BaseModel):
    id: str = Field(..., description="MongoDB document id")
    code: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class ExamTypeListResponse(BaseModel):
    items: List[ExamTypeOut]
    total: int


def exam_type_to_out(doc: ExamTypeDocument) -> ExamTypeOut:
    return ExamTypeOut(
        id=str(doc.id),
        code=doc.code,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
