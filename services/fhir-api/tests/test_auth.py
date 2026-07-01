"""Tests for SMART on FHIR discovery, authorization_code, and client_credentials grants."""

from __future__ import annotations

import httpx
import pytest

from app.core.security import decode_access_token


async def test_smart_configuration_advertises_endpoints(api_client: httpx.AsyncClient):
    resp = await api_client.get("/.well-known/smart-configuration")
    assert resp.status_code == 200
    body = resp.json()
    assert body["authorization_endpoint"].endswith("/oauth/authorize")
    assert body["token_endpoint"].endswith("/oauth/token")
    assert "patient/*.read" in body["scopes_supported"]


async def test_client_credentials_grant_issues_valid_jwt(api_client: httpx.AsyncClient):
    resp = await api_client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "healthbridge-analytics-service",
            "client_secret": "analytics-secret",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["scope"] == "system/*.read"

    decoded = decode_access_token(body["access_token"])
    assert decoded.client_id == "healthbridge-analytics-service"
    assert decoded.scope == "system/*.read"


async def test_client_credentials_grant_rejects_bad_secret(api_client: httpx.AsyncClient):
    resp = await api_client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "healthbridge-analytics-service",
            "client_secret": "wrong-secret",
        },
    )
    assert resp.status_code == 401


async def test_authorization_code_flow_end_to_end(api_client: httpx.AsyncClient):
    authorize_resp = await api_client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": "healthbridge-demo-app",
            "redirect_uri": "http://localhost:8501/callback",
            "scope": "patient/Patient.read launch/patient",
            "state": "xyz",
        },
        follow_redirects=False,
    )
    assert authorize_resp.status_code == 302
    location = authorize_resp.headers["location"]
    assert location.startswith("http://localhost:8501/callback?code=")
    assert "state=xyz" in location

    code = location.split("code=")[1].split("&")[0]

    token_resp = await api_client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:8501/callback",
            "client_id": "healthbridge-demo-app",
        },
    )
    assert token_resp.status_code == 200
    body = token_resp.json()
    assert body["patient"] == "example-patient-1"
    assert "patient/Patient.read" in body["scope"]

    # authorization codes are single-use
    replay_resp = await api_client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:8501/callback",
            "client_id": "healthbridge-demo-app",
        },
    )
    assert replay_resp.status_code == 400


async def test_authorize_rejects_scope_outside_client_allowlist(api_client: httpx.AsyncClient):
    resp = await api_client.get(
        "/oauth/authorize",
        params={
            "response_type": "code",
            "client_id": "healthbridge-demo-app",
            "redirect_uri": "http://localhost:8501/callback",
            "scope": "system/*.write",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400


async def test_protected_endpoint_requires_bearer_token(api_client: httpx.AsyncClient):
    resp = await api_client.get("/Patient")
    assert resp.status_code == 401


@pytest.mark.parametrize("bad_token", ["not-a-jwt", ""])
async def test_invalid_token_rejected(api_client: httpx.AsyncClient, bad_token: str):
    resp = await api_client.get("/Patient", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 401
