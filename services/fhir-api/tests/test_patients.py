"""Tests for Patient search/read/create, scope enforcement, and upstream error propagation."""

from __future__ import annotations

import httpx
import respx

from tests.conftest import FHIR_BASE, auth_headers

SAMPLE_PATIENT = {
    "resourceType": "Patient",
    "id": "example-patient-1",
    "active": True,
    "name": [{"family": "Osaro", "given": ["Nosa"]}],
    "gender": "male",
    "birthDate": "1990-05-01",
}

SAMPLE_BUNDLE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 1,
    "entry": [{"fullUrl": f"{FHIR_BASE}/Patient/example-patient-1", "resource": SAMPLE_PATIENT}],
}


async def test_search_patients_by_name_and_birthdate(
    api_client: httpx.AsyncClient, fhir_mock: respx.MockRouter, access_token: str
):
    route = fhir_mock.get("/Patient").mock(
        return_value=httpx.Response(200, json=SAMPLE_BUNDLE)
    )

    resp = await api_client.get(
        "/Patient",
        params={"name": "Osaro", "birthdate": "1990-05-01"},
        headers=auth_headers(access_token),
    )
    assert resp.status_code == 200
    assert route.called
    sent_params = dict(httpx.QueryParams(route.calls[0].request.url.params))
    assert sent_params["name"] == "Osaro"
    assert sent_params["birthdate"] == "1990-05-01"

    body = resp.json()
    assert body["total"] == 1
    assert body["entry"][0]["resource"]["id"] == "example-patient-1"


async def test_search_patients_response_is_cached(
    api_client: httpx.AsyncClient, fhir_mock: respx.MockRouter, access_token: str
):
    route = fhir_mock.get("/Patient").mock(return_value=httpx.Response(200, json=SAMPLE_BUNDLE))

    for _ in range(3):
        resp = await api_client.get(
            "/Patient", params={"name": "Osaro"}, headers=auth_headers(access_token)
        )
        assert resp.status_code == 200

    # Identical search params should hit HAPI FHIR once; subsequent calls are served from Redis.
    assert route.call_count == 1


async def test_get_patient_by_id(
    api_client: httpx.AsyncClient, fhir_mock: respx.MockRouter, access_token: str
):
    fhir_mock.get("/Patient/example-patient-1").mock(
        return_value=httpx.Response(200, json=SAMPLE_PATIENT)
    )

    resp = await api_client.get("/Patient/example-patient-1", headers=auth_headers(access_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "example-patient-1"
    assert body["name"][0]["family"] == "Osaro"


async def test_get_patient_propagates_upstream_404(
    api_client: httpx.AsyncClient, fhir_mock: respx.MockRouter, access_token: str
):
    fhir_mock.get("/Patient/does-not-exist").mock(
        return_value=httpx.Response(404, json={"resourceType": "OperationOutcome"})
    )

    resp = await api_client.get("/Patient/does-not-exist", headers=auth_headers(access_token))
    assert resp.status_code == 404


async def test_create_patient_requires_write_scope(
    api_client: httpx.AsyncClient, fhir_mock: respx.MockRouter, access_token: str
):
    # access_token fixture only grants system/*.read
    resp = await api_client.post(
        "/Patient", json=SAMPLE_PATIENT, headers=auth_headers(access_token)
    )
    assert resp.status_code == 403


async def test_create_patient_with_write_scope_succeeds(
    api_client: httpx.AsyncClient, fhir_mock: respx.MockRouter
):
    token_resp = await api_client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "healthbridge-analytics-service",
            "client_secret": "analytics-secret",
            "scope": "system/*.read",
        },
    )
    # Demonstrate scope negotiation: requesting a scope outside the allowlist is ignored/rejected,
    # so widen the fixture client's registry-backed scope for this write test via a fresh token
    # obtained with the broader allowed scope set on the client record.
    assert token_resp.status_code == 200

    fhir_mock.post("/Patient").mock(
        return_value=httpx.Response(201, json={**SAMPLE_PATIENT, "id": "new-id"})
    )

    from app.core.security import CLIENT_REGISTRY

    CLIENT_REGISTRY["healthbridge-analytics-service"].allowed_scopes.add("system/*.write")
    try:
        write_token_resp = await api_client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": "healthbridge-analytics-service",
                "client_secret": "analytics-secret",
                "scope": "system/*.write",
            },
        )
        assert write_token_resp.status_code == 200
        write_token = write_token_resp.json()["access_token"]

        resp = await api_client.post(
            "/Patient", json=SAMPLE_PATIENT, headers=auth_headers(write_token)
        )
        assert resp.status_code == 201
        assert resp.json()["id"] == "new-id"
    finally:
        CLIENT_REGISTRY["healthbridge-analytics-service"].allowed_scopes.discard("system/*.write")
