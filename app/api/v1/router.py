from fastapi import APIRouter

from app.api.v1.endpoints import exam_types, extract, files, papers, questions, subjects

api_router = APIRouter()
api_router.include_router(extract.router)
api_router.include_router(questions.router)
api_router.include_router(exam_types.router)
api_router.include_router(subjects.router)
api_router.include_router(papers.router)
api_router.include_router(files.router)
