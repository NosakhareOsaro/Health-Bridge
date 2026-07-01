"""Condition resource endpoints: read, search-by-patient/code, create."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.rate_limit import enforce_rate_limit
from app.core.search_cache import cached_search
from app.core.security import TokenData, require_scope
from app.fhir_client import FHIRClientError, get_fhir_client
from app.models.bundle import Bundle
from app.models.condition import Condition

router = APIRouter(prefix="/Condition", tags=["Condition"])


@router.get("", response_model=Bundle, dependencies=[Depends(enforce_rate_limit)])
async def search_conditions(
    patient: str | None = Query(default=None),
    code: str | None = Query(default=None, description="ICD-10 or SNOMED CT code"),
    clinical_status: str | None = Query(default=None, alias="clinical-status"),
    _count: int = Query(default=20, le=200),
    token: TokenData = Depends(require_scope("Condition", "read")),
) -> Bundle:
    params = {
        "patient": patient,
        "code": code,
        "clinical-status": clinical_status,
        "_count": _count,
    }

    async def fetch() -> dict:
        client = get_fhir_client()
        try:
            return await client.search("Condition", params)
        except FHIRClientError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    raw = await cached_search("Condition", params, fetch)
    return Bundle.from_fhir_json(raw)


@router.get("/{condition_id}", response_model=Condition, dependencies=[Depends(enforce_rate_limit)])
async def get_condition(
    condition_id: str,
    token: TokenData = Depends(require_scope("Condition", "read")),
) -> Condition:
    client = get_fhir_client()
    try:
        raw = await client.read("Condition", condition_id)
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Condition.model_validate(raw)


@router.post("", response_model=Condition, status_code=status.HTTP_201_CREATED)
async def create_condition(
    condition: Condition,
    token: TokenData = Depends(require_scope("Condition", "write")),
) -> Condition:
    client = get_fhir_client()
    try:
        raw = await client.create(
            "Condition", condition.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return Condition.model_validate(raw)
