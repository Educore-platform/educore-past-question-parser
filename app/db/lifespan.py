from contextlib import asynccontextmanager

from beanie import init_beanie
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.cache import close_redis, init_redis
from app.core.config import settings
from app.models.exam_file import ExamFileDocument
from app.models.exam_paper import ExamPaperDocument
from app.models.exam_type import ExamTypeDocument
from app.models.processing_job import ProcessingJobDocument
from app.models.question import QuestionDocument
from app.models.subject import SubjectDocument


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
    await init_beanie(
        database=app.state.mongo_client[settings.MONGODB_DB],
        document_models=[
            ExamTypeDocument,
            SubjectDocument,
            ExamPaperDocument,
            ExamFileDocument,
            QuestionDocument,
            ProcessingJobDocument,
        ],
    )
    await init_redis(settings.REDIS_URL)
    yield
    await close_redis()
    app.state.mongo_client.close()
