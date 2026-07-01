# ADR-0002: Use HAPI FHIR as the FHIR R4 server instead of building one from scratch

## Status

Accepted

## Context

The platform needs a spec-compliant FHIR R4 REST server that supports resource
CRUD, search parameters, and a `CapabilityStatement`. Options considered:

1. Build a minimal FHIR-shaped REST API directly in FastAPI, backed by a hand-rolled
   Postgres schema (e.g. one JSONB column per resource type).
2. Run [HAPI FHIR](https://hapifhir.io/), the reference open-source Java FHIR server, as
   the actual system of record, and put a purpose-built FastAPI gateway in front of it for
   SMART on FHIR auth, rate limiting, and caching.

## Decision

Run HAPI FHIR (`hapiproject/hapi` Docker image) as the FHIR R4 system of record. The
FastAPI service in `services/fhir-api` is a gateway/BFF in front of it, not a
reimplementation of FHIR itself.

## Rationale

- **Spec correctness is enormous surface area.** FHIR R4 search parameters (chained
  search, `_include`, modifiers like `:missing`/`:exact`), content negotiation
  (`application/fhir+json` vs `+xml`), conditional create/update, and validation against
  StructureDefinitions are each non-trivial to implement correctly. HAPI FHIR already does
  this, tested against the official FHIR test suite.
- **The interesting, differentiating work is the gateway, not the server.** SMART on FHIR
  OAuth2, JWT-scoped rate limiting, and Redis caching are what this project actually wants
  to demonstrate -- building a second, weaker FHIR server first would be wasted effort that
  adds risk without adding to what a reviewer can evaluate.
- **Realistic architecture.** Production FHIR deployments overwhelmingly either run HAPI
  FHIR (or a vendor-hosted equivalent) behind a purpose-built gateway for auth/policy
  concerns -- this mirrors that shape rather than a from-scratch toy.

## Consequences

- Adds a JVM-based service (and its own Postgres) to the Docker Compose stack, which is
  heavier than a pure-Python stack would have been.
- The FastAPI gateway's Pydantic models are a *subset* of full FHIR R4 (the fields this
  project actually uses), validated independently of HAPI FHIR's own more complete
  validation -- there is some duplication of "what does a valid Patient look like" logic
  between the two layers. This is called out in `services/fhir-api/README.md`.
- Upstream HAPI FHIR version upgrades are an external dependency the project doesn't
  control.
