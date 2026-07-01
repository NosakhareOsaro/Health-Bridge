"""Short-TTL Redis cache for read-heavy FHIR search results.

Clinical reference data (e.g. repeated population-health queries against the
same Observation code/date range) is read far more often than it changes.
Caching search responses for a short TTL takes load off both HAPI FHIR and
its underlying Postgres store without risking meaningfully stale reads.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from app.core.cache import get_redis

SEARCH_CACHE_TTL_SECONDS = 30


def _cache_key(resource_type: str, params: dict[str, Any]) -> str:
    normalized = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"fhir-search:{resource_type}:{digest}"


async def cached_search(
    resource_type: str,
    params: dict[str, Any],
    fetch_fn: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    redis_client = get_redis()
    key = _cache_key(resource_type, params)

    cached = await redis_client.get(key)
    if cached is not None:
        return json.loads(cached)

    result = await fetch_fn()
    await redis_client.set(key, json.dumps(result), ex=SEARCH_CACHE_TTL_SECONDS)
    return result
