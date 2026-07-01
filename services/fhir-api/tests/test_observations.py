"""Tests for Observation search-by-code/date and Pydantic value[x] validation."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.models.observation import Observation
from tests.conftest import auth_headers

SAMPLE_OBSERVATION = {
    "resourceType": "Observation",
    "id": "obs-1",
    "status": "final",
    "code": {"coding": [{"system": "http://loinc.org", "code": "8302-2", "display": "Height"}]},
    "subject": {"reference": "Patient/example-patient-1"},
    "effectiveDateTime": "2026-01-15T10:00:00Z",
    "valueQuantity": {"value": 180, "unit": "cm"},
}

SAMPLE_BUNDLE = {
    "resourceType": "Bundle",
    "type": "searchset",
    "total": 1,
    "entry": [{"resource": SAMPLE_OBSERVATION}],
}


async def test_search_observations_by_code_and_date(
    api_client: httpx.AsyncClient, fhir_mock: respx.MockRouter, access_token: str
):
    route = fhir_mock.get("/Observation").mock(return_value=httpx.Response(200, json=SAMPLE_BUNDLE))

    resp = await api_client.get(
        "/Observation",
        params={"code": "8302-2", "date": "2026-01-15"},
        headers=auth_headers(access_token),
    )
    assert resp.status_code == 200
    sent_params = dict(httpx.QueryParams(route.calls[0].request.url.params))
    assert sent_params["code"] == "8302-2"
    assert sent_params["date"] == "2026-01-15"


def test_observation_loinc_code_extraction():
    obs = Observation.model_validate(SAMPLE_OBSERVATION)
    assert obs.loinc_code() == "8302-2"


def test_observation_rejects_multiple_value_types():
    payload = {
        **SAMPLE_OBSERVATION,
        "valueString": "180 cm",  # conflicts with valueQuantity already set above
    }
    with pytest.raises(ValueError):
        Observation.model_validate(payload)
