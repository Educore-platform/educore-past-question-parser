"""
One-off: delete questions (and related papers/files) tied to a missing subject.

Usage (from project root):
  python scripts/cleanup_orphan_subject.py 69d37560

Uses MONGODB_URI, MONGODB_DB, REDIS_URL from the environment (same as the app).
"""

from __future__ import annotations

import asyncio
import os
import sys

from beanie import PydanticObjectId, init_beanie
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorClient

from app.core import cache
from app.core.config import settings
from app.models.exam_file import ExamFileDocument
from app.models.exam_paper import ExamPaperDocument
from app.models.exam_type import ExamTypeDocument
from app.models.question import QuestionDocument
from app.models.subject import SubjectDocument


async def main(prefix: str) -> None:
    prefix = prefix.strip().lower()
    if len(prefix) < 8 or any(c not in "0123456789abcdef" for c in prefix):
        raise SystemExit("prefix must be at least 8 hex characters")

    client = AsyncIOMotorClient(settings.MONGODB_URI)
    try:
        await init_beanie(
            database=client[settings.MONGODB_DB],
            document_models=[
                ExamTypeDocument,
                SubjectDocument,
                ExamPaperDocument,
                ExamFileDocument,
                QuestionDocument,
            ],
        )
        await cache.init_redis(settings.REDIS_URL)

        raw_ids = await QuestionDocument.distinct("subject_id")
        candidates: list[PydanticObjectId] = []
        for raw in raw_ids:
            if raw is None:
                continue
            try:
                oid = PydanticObjectId(str(raw))
            except (ValueError, TypeError, InvalidId):
                continue
            if not str(oid).lower().startswith(prefix):
                continue
            subj = await SubjectDocument.get(oid)
            if subj is None:
                candidates.append(oid)

        if not candidates:
            print("No orphan subject_id on questions matches that prefix.")
            return
        if len(candidates) > 1:
            print("Multiple matching orphan subject_ids; aborting:", [str(c) for c in candidates])
            raise SystemExit(1)

        orphan_id = candidates[0]
        print(f"Resolved orphan subject_id: {orphan_id}")

        q_del = await QuestionDocument.find(QuestionDocument.subject_id == orphan_id).delete()
        q_n = q_del.deleted_count if q_del else 0
        print(f"Deleted {q_n} question(s)")

        papers = await ExamPaperDocument.find(ExamPaperDocument.subject_id == orphan_id).to_list()
        paper_ids = [p.id for p in papers if p.id is not None]
        if paper_ids:
            f_del = await ExamFileDocument.find(
                {"paper_id": {"$in": paper_ids}}
            ).delete()
            f_n = f_del.deleted_count if f_del else 0
            print(f"Deleted {f_n} exam file record(s)")
            p_del = await ExamPaperDocument.find(ExamPaperDocument.subject_id == orphan_id).delete()
            p_n = p_del.deleted_count if p_del else 0
            print(f"Deleted {p_n} exam paper(s)")
        else:
            print("No exam papers referenced this subject_id")

        await cache.delete("question:stats")
        await cache.delete_pattern("question:filters:*")
        await cache.delete_pattern("question:*")
        print("Cleared question-related Redis cache keys")
    finally:
        await cache.close_redis()
        client.close()


if __name__ == "__main__":
    pfx = os.environ.get("ORPHAN_SUBJECT_PREFIX", (sys.argv[1] if len(sys.argv) > 1 else ""))
    if not pfx:
        raise SystemExit("usage: python scripts/cleanup_orphan_subject.py <8+ hex prefix>")
    asyncio.run(main(pfx))
