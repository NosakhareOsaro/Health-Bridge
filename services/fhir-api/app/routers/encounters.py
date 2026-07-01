"""Encounter resource endpoints: read, search-by-patient/status/date, create."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.rate_limit import enforce_rate_limit
from app.core.search_cache import cached_search
from app.core.security import TokenData, require_scope
from app.fhir_client import FHIRClientError, get_fhir_client
from app.models.bundle import Bundle
from app.models.encounter import Encounter

router = APIRouter(prefix="/Encounter", tags=["Encounter"])


@router.get("", response_model=Bundle, dependencies=[Depends(enforce_rate_limit)])
async def search_encounters(
    patient: str | None = Query(default=None, description="Patient/{id} reference"),
    status_: str | None = Query(default=None, alias="status"),
    date_: date | None = Query(default=None, alias="date"),
    _count: int = Query(default=20, le=200),
    token: TokenData = Depends(require_scope("Encounter", "read")),
) -> Bundle:
    params = {
        "patient": patient,
        "status": status_,
        "date": date_.isoformat() if date_ else None,
        "_count": _count,
    }

    async def fetch() -> dict:
        client = get_fhir_client()
        try:
            return await client.search("Encounter", params)
        except FHIRClientError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    raw = await cached_search("Encounter", params, fetch)
    return Bundle.from_fhir_json(raw)


@router.get("/{encounter_id}", response_model=Encounter, dependencies=[Depends(enforce_rate_limit)])
async def get_encounter(
    encounter_id: str,
    token: TokenData = Depends(require_scope("Encounter", "read")),
) -> Encounter:
    client = get_fhir_client()
    try:
        raw = await client.read("Encounter", encounter_id)
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Encounter.model_validate(raw)


@router.post("", response_model=Encounter, status_code=status.HTTP_201_CREATED)
async def create_encounter(
    encounter: Encounter,
    token: TokenData = Depends(require_scope("Encounter", "write")),
) -> Encounter:
    client = get_fhir_client()
    try:
        raw = await client.create(
            "Encounter", encounter.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Encounter.model_validate(raw)
