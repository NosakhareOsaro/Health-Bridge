"""Tests for the Redis-backed, JWT-identity-scoped rate limiter."""

from __future__ import annotations

import httpx
import respx

from app.core.config import settings
from tests.conftest import auth_headers

SAMPLE_BUNDLE = {"resourceType": "Bundle", "type": "searchset", "total": 0, "entry": []}


async def test_rate_limit_returns_429_after_threshold(
    api_client: httpx.AsyncClient, fhir_mock: respx.MockRouter, access_token: str, monkeypatch
):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    fhir_mock.get("/Patient").mock(return_value=httpx.Response(200, json=SAMPLE_BUNDLE))

    statuses = []
    for _ in range(5):
        resp = await api_client.get("/Patient", headers=auth_headers(access_token))
        statuses.append(resp.status_code)

    assert statuses[:3] == [200, 200, 200]
    assert 429 in statuses
    limited_index = statuses.index(429)
    assert statuses[limited_index] == 429


async def test_rate_limit_is_scoped_per_identity(
    api_client: httpx.AsyncClient, fhir_mock: respx.MockRouter, monkeypatch
):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 1)
    fhir_mock.get("/Patient").mock(return_value=httpx.Response(200, json=SAMPLE_BUNDLE))

    async def get_token(client_id: str) -> str:
        resp = await api_client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": "analytics-secret",
            },
        )
        return resp.json()["access_token"]

    token_a = await get_token("healthbridge-analytics-service")

    first = await api_client.get("/Patient", headers=auth_headers(token_a))
    second = await api_client.get("/Patient", headers=auth_headers(token_a))
    assert first.status_code == 200
    assert second.status_code == 429
