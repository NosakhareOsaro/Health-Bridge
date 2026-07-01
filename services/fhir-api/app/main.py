"""HealthBridge FHIR Gateway: SMART-on-FHIR FastAPI service in front of HAPI FHIR.

Responsibilities:

- Terminate SMART on FHIR OAuth2 (authorization_code + client_credentials)
- Validate/serialize FHIR R4 resources with Pydantic v2 models
- Enforce per-identity, JWT-scoped rate limiting via Redis
- Cache read-heavy search responses in Redis
- Proxy validated requests to the upstream HAPI FHIR server (system of record)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    auth,
    conditions,
    encounters,
    metadata,
    molecular_sequences,
    observations,
    patients,
)

app = FastAPI(
    title=settings.app_name,
    description=(
        "SMART on FHIR R4 gateway providing OAuth2-secured, rate-limited, "
        "cached access to Patient/Encounter/Condition/Observation/"
        "MolecularSequence resources backed by a HAPI FHIR server."
    ),
    version="0.1.0",
    contact={"name": "HealthBridge"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metadata.router)
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(encounters.router)
app.include_router(conditions.router)
app.include_router(observations.router)
app.include_router(molecular_sequences.router)
