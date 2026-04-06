from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    message: str = Field(..., example="EduCore PDF Extractor is running")
    docs: str = Field(..., example="/docs")
    openapi: str = Field(..., example="/openapi.json")


class PdfUploadResponse(BaseModel):
    """Metadata after a PDF is stored on disk."""

    stored_filename: str = Field(..., description="Unique filename under data/uploads")
    original_filename: str
    absolute_path: str = Field(..., description="Full path on the server filesystem")
    relative_path: str = Field(..., description="Path relative to project root")
    size_bytes: int


class PageText(BaseModel):
    page: int
    text: str


class ExtractRawResponse(BaseModel):
    filename: str
    stored_filename: Optional[str] = Field(None, description="Set when the file was persisted")
    total_pages: int
    pages: List[PageText]


class ExtractQuestionsUploadSummary(BaseModel):
    """Metadata after upload, parse, and persist — no question bodies (use GET /questions)."""

    filename: str
    stored_filename: Optional[str] = None
    total_pages: int
    years_detected: List[str]
    total_questions: int = Field(
        ...,
        description="Number of questions parsed from the PDF this run",
    )
    persisted_count: int = Field(
        0,
        description="Number of questions inserted into MongoDB for this request",
    )
    paper_id: Optional[str] = Field(
        None,
        description="ExamPaper id for this upload; use with GET /questions?paper_id=",
    )
    paper_code: Optional[str] = Field(
        None,
        description="Subject-scoped sequence for this upload (e.g. 001, 002)",
    )
    subject_name: Optional[str] = Field(
        None,
        description="Canonical subject name (e.g. 'Economics')",
    )


class ExtractQuestionsMultiUploadSummary(BaseModel):
    """Multi-file upload: one summary per PDF (each file has its own ``paper_id``)."""

    results: List[ExtractQuestionsUploadSummary]
    file_count: int = Field(..., description="Number of PDFs processed")
    total_size_bytes: int = Field(..., description="Combined size of uploaded PDFs")


ExtractQuestionsResponse = ExtractQuestionsUploadSummary


class YearBreakdown(BaseModel):
    total: int
    with_answers: int
    with_options: int


class ExtractStatsResponse(BaseModel):
    filename: str
    stored_filename: Optional[str] = None
    total_pages: int
    total_questions: int
    breakdown_by_year: dict[str, YearBreakdown]


class DistinctValuesResponse(BaseModel):
    """Distinct filter values available across questions/subjects."""

    subjects: List[str]
    exam_types: List[str] = Field(
        ...,
        description="Distinct exam type codes from the exam_types registry",
    )
    years: List[str]


class QuestionStatsResponse(BaseModel):
    """High-level counts for the questions collection."""

    total: int
    by_subject: Dict[str, int]
    by_exam_type: Dict[str, int]
    by_year: Dict[str, int]


class ImportGroupInfo(BaseModel):
    """Aggregate info for one uploaded PDF (exam paper + linked exam file)."""

    paper_id: str
    exam_file_id: Optional[str] = Field(None, description="ExamFile document id")
    subject_id: Optional[str] = None
    exam_type_id: Optional[str] = Field(None, description="ExamType document id")
    paper_code: Optional[str] = None
    subject: str
    exam_type: str = Field(..., alias="examType")
    year: Optional[str] = None
    years_detected: List[str] = Field(default_factory=list)
    total_questions: int
    total_pages: int = 0
    source_original_filename: Optional[str] = Field(
        None,
        description="Original PDF filename for this upload",
    )
    stored_filename: Optional[str] = Field(
        None,
        description="Unique filename on disk under the upload directory",
    )
    relative_path: Optional[str] = Field(
        None,
        description="Path to the PDF relative to project root",
    )
    size_bytes: Optional[int] = Field(None, description="PDF file size in bytes")
    created_at: str

    model_config = {"populate_by_name": True}


class ImportGroupListResponse(BaseModel):
    """List of exam paper imports."""

    items: List[ImportGroupInfo]
    total: int = 0
