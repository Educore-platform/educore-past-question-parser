"""
Async Redis wrapper used throughout the application.

All public functions degrade gracefully: if Redis is unavailable (connection
error, timeout, etc.) they log a warning and return a safe default so callers
can fall back to MongoDB without crashing.

Initialise once at startup via ``init_redis(url)`` and tear down via
``close_redis()``.  The internal ``_redis`` singleton is intentionally
module-level so every part of the app shares one connection pool.
"""

import json
import logging
from typing import Any, Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


async def init_redis(url: str) -> None:
    global _redis
    _redis = aioredis.from_url(url, decode_responses=True)
    try:
        await _redis.ping()
        logger.info("Redis connected: %s", url)
    except Exception as exc:
        logger.warning("Redis ping failed (%s) — caching disabled until reconnect", exc)


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")


def _get() -> Optional[aioredis.Redis]:
    return _redis


# ---------------------------------------------------------------------------
# JSON cache helpers
# ---------------------------------------------------------------------------


async def get_json(key: str) -> Optional[Any]:
    """Return the deserialised value stored at *key*, or ``None`` on miss/error."""
    r = _get()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:
        logger.warning("Redis GET %s failed: %s", key, exc)
        return None


async def set_json(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """Serialise *value* to JSON and store it at *key* with an optional TTL (seconds)."""
    r = _get()
    if r is None:
        return
    try:
        payload = json.dumps(value, default=str)
        if ttl is not None:
            await r.set(key, payload, ex=ttl)
        else:
            await r.set(key, payload)
    except Exception as exc:
        logger.warning("Redis SET %s failed: %s", key, exc)


# ---------------------------------------------------------------------------
# Raw string helpers (used by paper_code_service)
# ---------------------------------------------------------------------------


async def set_raw(key: str, value: str) -> None:
    """Store a plain string value with no TTL."""
    r = _get()
    if r is None:
        return
    try:
        await r.set(key, value)
    except Exception as exc:
        logger.warning("Redis SET (raw) %s failed: %s", key, exc)


# ---------------------------------------------------------------------------
# Key management
# ---------------------------------------------------------------------------


async def delete(*keys: str) -> None:
    """Delete one or more keys."""
    r = _get()
    if r is None or not keys:
        return
    try:
        await r.delete(*keys)
    except Exception as exc:
        logger.warning("Redis DELETE %s failed: %s", keys, exc)


async def delete_pattern(pattern: str) -> None:
    """
    Delete all keys matching *pattern*.

    Uses ``SCAN`` with a cursor (never ``KEYS``) to avoid blocking Redis on
    large keyspaces.
    """
    r = _get()
    if r is None:
        return
    try:
        cursor = 0
        while True:
            cursor, batch = await r.scan(cursor=cursor, match=pattern, count=100)
            if batch:
                await r.delete(*batch)
            if cursor == 0:
                break
    except Exception as exc:
        logger.warning("Redis SCAN/DELETE pattern %s failed: %s", pattern, exc)


async def exists(key: str) -> bool:
    """Return ``True`` if *key* exists in Redis."""
    r = _get()
    if r is None:
        return False
    try:
        return bool(await r.exists(key))
    except Exception as exc:
        logger.warning("Redis EXISTS %s failed: %s", key, exc)
        return False


# ---------------------------------------------------------------------------
# Atomic counter (used by paper_code_service)
# ---------------------------------------------------------------------------


async def incr(key: str) -> Optional[int]:
    """
    Atomically increment *key* and return the new value.

    Returns ``None`` if Redis is unavailable.
    """
    r = _get()
    if r is None:
        return None
    try:
        return await r.incr(key)
    except Exception as exc:
        logger.warning("Redis INCR %s failed: %s", key, exc)
        return None


async def set_if_not_exists(key: str, value: int) -> bool:
    """
    Set *key* to *value* only if the key does not already exist (SET NX).

    Returns ``True`` if the key was set, ``False`` if it already existed or
    Redis is unavailable.
    """
    r = _get()
    if r is None:
        return False
    try:
        return bool(await r.setnx(key, value))
    except Exception as exc:
        logger.warning("Redis SETNX %s failed: %s", key, exc)
        return False


# ---------------------------------------------------------------------------
# List helpers (used by paper_code_service pool)
# ---------------------------------------------------------------------------


async def lpop(key: str) -> Optional[str]:
    """Pop and return the leftmost element of the list at *key*, or ``None``."""
    r = _get()
    if r is None:
        return None
    try:
        return await r.lpop(key)
    except Exception as exc:
        logger.warning("Redis LPOP %s failed: %s", key, exc)
        return None


async def rpush(key: str, *values: str) -> None:
    """Append *values* to the right end of the list at *key*."""
    r = _get()
    if r is None:
        return
    try:
        await r.rpush(key, *values)
    except Exception as exc:
        logger.warning("Redis RPUSH %s failed: %s", key, exc)


async def llen(key: str) -> int:
    """Return the length of the list at *key*, or 0 on miss/error."""
    r = _get()
    if r is None:
        return 0
    try:
        return await r.llen(key)
    except Exception as exc:
        logger.warning("Redis LLEN %s failed: %s", key, exc)
        return 0
