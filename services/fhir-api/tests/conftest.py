"""Shared pytest fixtures: fake Redis, mocked HAPI FHIR transport, and an ASGI test client."""

from __future__ import annotations

import fakeredis
import httpx
import pytest
import pytest_asyncio
import respx

from app.core.cache import set_redis_client
from app.fhir_client import FHIRClient, set_fhir_client
from app.main import app

FHIR_BASE = "http://upstream-hapi-fhir.test/fhir"


@pytest.fixture(autouse=True)
def fake_redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    set_redis_client(client)
    yield client


@pytest_asyncio.fixture
async def fhir_mock():
    with respx.mock(base_url=FHIR_BASE, assert_all_called=False) as mock:
        client = FHIRClient(base_url=FHIR_BASE)
        set_fhir_client(client)
        yield mock
        await client.aclose()


@pytest_asyncio.fixture
async def api_client(fhir_mock):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def access_token(api_client: httpx.AsyncClient) -> str:
    """Obtains a client_credentials token scoped to system/*.read for test use."""
    resp = await api_client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "healthbridge-analytics-service",
            "client_secret": "analytics-secret",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
