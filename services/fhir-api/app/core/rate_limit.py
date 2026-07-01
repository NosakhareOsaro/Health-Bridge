"""JWT-identity-aware rate limiting backed by Redis fixed-window counters.

Each bearer token's ``sub`` claim (falling back to ``client_id``) is used as
the rate-limit bucket key, so limits are enforced per authenticated caller
rather than per IP address -- appropriate for a token-gated FHIR API where
many clients may share a NAT gateway.
"""

from __future__ import annotations

import time

from fastapi import Depends, HTTPException, status

from app.core.cache import get_redis
from app.core.config import settings
from app.core.security import TokenData, get_current_token


async def enforce_rate_limit(token: TokenData = Depends(get_current_token)) -> TokenData:
    identity = token.sub or token.client_id or "anonymous"
    window = int(time.time() // 60)  # fixed 60s window
    key = f"ratelimit:{identity}:{window}"

    redis_client = get_redis()
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expire(key, 60)

    if current > settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Rate limit exceeded: {settings.rate_limit_per_minute} requests/minute "
                f"for subject '{identity}'"
            ),
            headers={"Retry-After": "60"},
        )
    return token
