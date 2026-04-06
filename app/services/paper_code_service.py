"""
Redis-backed paper code pool.

Paper codes are subject-scoped zero-padded sequence strings ("001", "002", …)
that identify each uploaded PDF within a subject.  The original implementation
counted ``exam_papers`` in MongoDB and added 1, which races when two PDFs for
the same subject are processed concurrently.

This module replaces that with:
  - An atomic Redis ``INCR`` counter per subject (``paper_code:counter:{id}``).
  - A FIFO list of pre-generated codes (``paper_code:pool:{id}``).
  - A background refill task that fires when the pool drops to ≤ 25 % capacity,
    so the main request path is never delayed by code generation.

Graceful fallback: if Redis is unavailable every function degrades to the
original MongoDB-count approach so no upload is ever blocked.
"""

import asyncio
import logging
from typing import Optional

from beanie import PydanticObjectId

from app.core import cache
from app.core.config import settings

logger = logging.getLogger(__name__)

_COUNTER_PREFIX = "paper_code:counter:"
_POOL_PREFIX = "paper_code:pool:"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _counter_key(subject_id: str) -> str:
    return f"{_COUNTER_PREFIX}{subject_id}"


def _pool_key(subject_id: str) -> str:
    return f"{_POOL_PREFIX}{subject_id}"


def _fmt(n: int) -> str:
    """Format a sequence integer as a zero-padded code (minimum width 3)."""
    return str(n).zfill(max(3, len(str(n))))


async def _seed_counter(subject_id: str) -> int:
    """
    Seed the Redis counter from the current MongoDB exam_papers count for this
    subject.  Uses SET NX so concurrent callers are safe — only one will win
    and the rest will read the existing value.

    Returns the current counter value (i.e. the count of already-stored papers).
    """
    from app.models.exam_paper import ExamPaperDocument

    try:
        oid = PydanticObjectId(subject_id)
    except Exception:
        return 0

    count = await ExamPaperDocument.find(
        ExamPaperDocument.subject_id == oid
    ).count()

    key = _counter_key(subject_id)
    await cache.set_if_not_exists(key, count)

    # Read back the authoritative value (in case another process seeded first)
    raw = await cache.get_json(key)
    try:
        return int(raw) if raw is not None else count
    except (TypeError, ValueError):
        return count


async def _generate_batch(subject_id: str, batch_size: int) -> list[str]:
    """
    Atomically increment the counter *batch_size* times and return the
    resulting formatted codes.  Returns an empty list if Redis is unavailable.
    """
    codes: list[str] = []
    for _ in range(batch_size):
        n = await cache.incr(_counter_key(subject_id))
        if n is None:
            return []
        codes.append(_fmt(n))
    return codes


async def _refill_pool(subject_id: str) -> None:
    """Generate a fresh batch and push it onto the right end of the pool list."""
    batch_size = settings.PAPER_CODE_BATCH_SIZE
    try:
        codes = await _generate_batch(subject_id, batch_size)
        if codes:
            await cache.rpush(_pool_key(subject_id), *codes)
            logger.debug(
                "paper_code pool refilled for subject %s: %s", subject_id, codes
            )
    except Exception as exc:
        logger.warning("paper_code pool refill failed for %s: %s", subject_id, exc)


async def _ensure_pool(subject_id: str) -> None:
    """
    If the pool is empty, seed the counter then generate the first batch.
    Called synchronously (awaited) before the first LPOP.
    """
    pool_key = _pool_key(subject_id)
    remaining = await cache.llen(pool_key)
    if remaining == 0:
        await _seed_counter(subject_id)
        codes = await _generate_batch(subject_id, settings.PAPER_CODE_BATCH_SIZE)
        if codes:
            await cache.rpush(pool_key, *codes)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_next_paper_code(subject_id: PydanticObjectId) -> str:
    """
    Return the next paper code for *subject_id*.

    1. Ensures the pool is non-empty (seeds on first use).
    2. POPs one code from the front of the Redis list.
    3. If the remaining pool has dropped to ≤ 25 % of batch size, schedules a
       background refill without blocking the caller.
    4. Falls back to the original MongoDB count approach if Redis is down.
    """
    sid = str(subject_id)
    pool_key = _pool_key(sid)

    try:
        await _ensure_pool(sid)
        code = await cache.lpop(pool_key)

        if code is not None:
            remaining = await cache.llen(pool_key)
            threshold = int(
                settings.PAPER_CODE_BATCH_SIZE * settings.PAPER_CODE_REFILL_THRESHOLD
            )
            if remaining <= threshold:
                asyncio.create_task(_refill_pool(sid))
            return code

    except Exception as exc:
        logger.warning(
            "paper_code pool unavailable for subject %s (%s) — falling back to MongoDB count",
            sid,
            exc,
        )

    # Fallback: count existing papers and add 1 (original behaviour)
    return await _fallback_paper_code(subject_id)


async def _fallback_paper_code(subject_id: PydanticObjectId) -> str:
    """Original MongoDB-count approach used when Redis is unavailable."""
    from app.models.exam_paper import ExamPaperDocument

    count = await ExamPaperDocument.find(
        ExamPaperDocument.subject_id == subject_id
    ).count()
    next_n = count + 1
    return _fmt(next_n)


async def warm_pool(subject_id: PydanticObjectId) -> None:
    """
    Explicitly pre-warm the pool for a subject.  Call this after creating a
    new subject if you want codes ready before the first upload arrives.
    """
    sid = str(subject_id)
    await _ensure_pool(sid)
    logger.info("paper_code pool warmed for subject %s", sid)
