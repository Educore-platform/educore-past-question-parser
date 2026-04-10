import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.db.lifespan import lifespan

# Simple logging setup
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(levelname)s: %(message)s",
    force=True
)

# Silence chatty third-party loggers
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("motor").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

OPENAPI_TAGS = [
    {
        "name": "system",
        "description": "Service metadata and links to interactive API documentation (Swagger UI).",
    },
    {
        "name": "extract",
        "description": (
            "Upload one or more PDFs, extract JAMB/WAEC-style MCQs, and persist them to MongoDB. "
            "Each request creates an ExamPaper and ExamFile record per source file."
        ),
    },
    {
        "name": "questions",
        "description": (
            "Manage extracted questions. List with filters and pagination, "
            "view lightweight summaries, aggregate stats, available filter values, "
            "or fetch/update/delete a single document by id."
        ),
    },
    {
        "name": "papers",
        "description": (
            "Exam paper imports — one record per uploaded PDF. "
            "List with filters, fetch by id, or delete (cascades to questions and file record)."
        ),
    },
    {
        "name": "files",
        "description": (
            "Exam file records — PDF storage metadata (filename, hash, size, page count). "
            "Read-only; records are created automatically during extraction."
        ),
    },
    {
        "name": "exam-types",
        "description": (
            "Exam type registry (e.g. JAMB, WAEC). "
            "Full CRUD; deletion is blocked while subjects reference the exam type."
        ),
    },
    {
        "name": "subjects",
        "description": (
            "Subject registry (e.g. Biology, Government). "
            "Full CRUD; deletion is blocked while exam papers reference the subject."
        ),
    },
]

app = FastAPI(
    title="EduCore PDF Parser",
    description=(
        "REST API for extracting and structuring past questions from JAMB/WAEC-style PDFs. "
        "Use **Swagger UI** at `/docs` to try multipart uploads interactively. "
        "Uploaded PDFs are saved to **Cloudinary**; structured questions "
        "are stored in **MongoDB** (configure `MONGODB_URI` / `MONGODB_DB`)."
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

@app.get("/", tags=["system"], summary="Service info")
def root():
    """Basic health check and service info."""
    return {
        "success": True,
        "message": "EduCore PDF Parser is running",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health", tags=["system"], summary="Health check")
def health():
    """Railway health check endpoint."""
    return root()


register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
