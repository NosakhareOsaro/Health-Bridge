"""Patient resource endpoints: read, search-by-name/birthdate/gender, create."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.rate_limit import enforce_rate_limit
from app.core.search_cache import cached_search
from app.core.security import TokenData, require_scope
from app.fhir_client import FHIRClientError, get_fhir_client
from app.models.bundle import Bundle
from app.models.patient import Patient

router = APIRouter(prefix="/Patient", tags=["Patient"])


@router.get("", response_model=Bundle, dependencies=[Depends(enforce_rate_limit)])
async def search_patients(
    name: str | None = Query(default=None, description="Matches Patient.name (family or given)"),
    birthdate: date | None = Query(default=None, description="Exact match on Patient.birthDate"),
    gender: str | None = Query(default=None),
    identifier: str | None = Query(default=None),
    _count: int = Query(default=20, le=200),
    token: TokenData = Depends(require_scope("Patient", "read")),
) -> Bundle:
    params = {
        "name": name,
        "birthdate": birthdate.isoformat() if birthdate else None,
        "gender": gender,
        "identifier": identifier,
        "_count": _count,
    }

    async def fetch() -> dict:
        client = get_fhir_client()
        try:
            return await client.search("Patient", params)
        except FHIRClientError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    raw = await cached_search("Patient", params, fetch)
    return Bundle.from_fhir_json(raw)


@router.get("/{patient_id}", response_model=Patient, dependencies=[Depends(enforce_rate_limit)])
async def get_patient(
    patient_id: str,
    token: TokenData = Depends(require_scope("Patient", "read")),
) -> Patient:
    client = get_fhir_client()
    try:
        raw = await client.read("Patient", patient_id)
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Patient.model_validate(raw)


@router.post("", response_model=Patient, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient: Patient,
    token: TokenData = Depends(require_scope("Patient", "write")),
) -> Patient:
    client = get_fhir_client()
    try:
        raw = await client.create("Patient", patient.model_dump(mode="json", by_alias=True, exclude_none=True))
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Patient.model_validate(raw)
