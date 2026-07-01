"""Observation resource endpoints: read, search-by-code/date/patient, create."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.rate_limit import enforce_rate_limit
from app.core.search_cache import cached_search
from app.core.security import TokenData, require_scope
from app.fhir_client import FHIRClientError, get_fhir_client
from app.models.bundle import Bundle
from app.models.observation import Observation

router = APIRouter(prefix="/Observation", tags=["Observation"])


@router.get("", response_model=Bundle, dependencies=[Depends(enforce_rate_limit)])
async def search_observations(
    patient: str | None = Query(default=None),
    code: str | None = Query(default=None, description="e.g. a LOINC code"),
    date_: date | None = Query(default=None, alias="date"),
    _count: int = Query(default=20, le=200),
    token: TokenData = Depends(require_scope("Observation", "read")),
) -> Bundle:
    params = {
        "patient": patient,
        "code": code,
        "date": date_.isoformat() if date_ else None,
        "_count": _count,
    }

    async def fetch() -> dict:
        client = get_fhir_client()
        try:
            return await client.search("Observation", params)
        except FHIRClientError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    raw = await cached_search("Observation", params, fetch)
    return Bundle.from_fhir_json(raw)


@router.get(
    "/{observation_id}", response_model=Observation, dependencies=[Depends(enforce_rate_limit)]
)
async def get_observation(
    observation_id: str,
    token: TokenData = Depends(require_scope("Observation", "read")),
) -> Observation:
    client = get_fhir_client()
    try:
        raw = await client.read("Observation", observation_id)
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Observation.model_validate(raw)


@router.post("", response_model=Observation, status_code=status.HTTP_201_CREATED)
async def create_observation(
    observation: Observation,
    token: TokenData = Depends(require_scope("Observation", "write")),
) -> Observation:
    client = get_fhir_client()
    try:
        raw = await client.create(
            "Observation", observation.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Observation.model_validate(raw)
