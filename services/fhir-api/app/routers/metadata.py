"""Health check and proxied FHIR CapabilityStatement."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.fhir_client import FHIRClientError, get_fhir_client

router = APIRouter(tags=["System"])


@router.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok"}


@router.get("/metadata")
async def capability_statement() -> dict:
    """Passthrough of the upstream HAPI FHIR CapabilityStatement (unauthenticated, per FHIR spec)."""
    client = get_fhir_client()
    try:
        return await client.capabilities()
    except FHIRClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
