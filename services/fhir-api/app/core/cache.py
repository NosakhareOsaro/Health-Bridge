"""Redis client factory shared by the rate limiter and the FHIR search cache."""

from __future__ import annotations

import redis.asyncio as redis

from app.core.config import settings

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def set_redis_client(client: redis.Redis) -> None:
    """Test hook: inject a fake/mock Redis client (e.g. fakeredis)."""
    global _redis_client
    _redis_client = client
