"""MolecularSequence resource endpoints: read, search-by-patient/type."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.rate_limit import enforce_rate_limit
from app.core.search_cache import cached_search
from app.core.security import TokenData, require_scope
from app.fhir_client import FHIRClientError, get_fhir_client
from app.models.bundle import Bundle
from app.models.molecular_sequence import MolecularSequence

router = APIRouter(prefix="/MolecularSequence", tags=["MolecularSequence"])


@router.get("", response_model=Bundle, dependencies=[Depends(enforce_rate_limit)])
async def search_molecular_sequences(
    patient: str | None = Query(default=None),
    type_: str | None = Query(default=None, alias="type"),
    _count: int = Query(default=20, le=200),
    token: TokenData = Depends(require_scope("MolecularSequence", "read")),
) -> Bundle:
    params = {"patient": patient, "type": type_, "_count": _count}

    async def fetch() -> dict:
        client = get_fhir_client()
        try:
            return await client.search("MolecularSequence", params)
        except FHIRClientError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    raw = await cached_search("MolecularSequence", params, fetch)
    return Bundle.from_fhir_json(raw)


@router.get(
    "/{sequence_id}",
    response_model=MolecularSequence,
    dependencies=[Depends(enforce_rate_limit)],
)
async def get_molecular_sequence(
    sequence_id: str,
    token: TokenData = Depends(require_scope("MolecularSequence", "read")),
) -> MolecularSequence:
    client = get_fhir_client()
    try:
        raw = await client.read("MolecularSequence", sequence_id)
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return MolecularSequence.model_validate(raw)
