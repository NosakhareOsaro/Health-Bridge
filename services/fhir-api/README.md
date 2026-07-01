# fhir-api

A SMART on FHIR R4 gateway built with FastAPI + Pydantic v2, sitting in front of a
[HAPI FHIR](https://hapifhir.io/) server (the actual system of record for clinical resources).

## What this service does

- **OAuth2 / SMART on FHIR** (`app/core/security.py`, `app/routers/auth.py`): a minimal
  authorization server implementing the `authorization_code` grant (standalone SMART app
  launch) and `client_credentials` grant (SMART Backend Services), SMART v1 scope strings
  (`patient/Observation.read`, `system/*.read`, `launch/patient`, ...), and HS256 JWT access
  tokens signed via Authlib's `jose` module.
- **Resource models** (`app/models/`): Pydantic v2 models for `Patient`, `Encounter`,
  `Condition`, `Observation`, and `MolecularSequence`, with real FHIR-shaped validation
  (choice-type `value[x]` enforcement on `Observation`, no-future-birthdate on `Patient`, etc.)
  and small domain helpers (`Encounter.length_of_stay_hours()`, `Condition.icd10_codes()`).
- **Search parameters**: Patient by `name`/`birthdate`/`gender`/`identifier`, Encounter by
  `patient`/`status`/`date`, Condition by `patient`/`code`/`clinical-status`, Observation by
  `patient`/`code`/`date`, MolecularSequence by `patient`/`type`.
- **Rate limiting** (`app/core/rate_limit.py`): fixed-window limiter keyed on the JWT `sub`
  claim, backed by Redis `INCR`/`EXPIRE`.
- **Caching** (`app/core/search_cache.py`): 30s TTL cache of search responses in Redis, keyed
  by a hash of the resource type + query params.
- **OpenAPI docs**: auto-generated at `/docs` (Swagger UI) and `/redoc`.

## Running locally

```bash
docker compose up hapi-fhir fhir-db redis fhir-api
# API now listening on http://localhost:8000, docs at http://localhost:8000/docs
```

Or without Docker:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # adjust FHIR_UPSTREAM_URL / REDIS_URL as needed
uvicorn app.main:app --reload
```

## Getting a token

```bash
# SMART Backend Services (system-to-system)
curl -X POST http://localhost:8000/oauth/token \
  -d grant_type=client_credentials \
  -d client_id=healthbridge-analytics-service \
  -d client_secret=analytics-secret

# Use it:
curl http://localhost:8000/Patient?name=Smith \
  -H "Authorization: Bearer <access_token>"
```

The demo client registry lives in `app/core/security.py::CLIENT_REGISTRY` -- swap this
in-memory dict for a persistent, encrypted client store before any real deployment.

## Tests

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

Tests mock the upstream HAPI FHIR HTTP calls with `respx` and use `fakeredis` for the
rate limiter/cache, so the full suite runs without Docker or network access.

## Known simplifications (portfolio scope)

- The OAuth2 authorization server is in-memory (clients, auth codes) -- fine for a demo,
  not for production multi-instance deployment.
- `/oauth/authorize` auto-approves consent since there's no real end-user identity/login
  screen; a production SMART launch would authenticate the end user first.
- PKCE is advertised as unsupported (`code_challenge_methods_supported: []`) -- would be a
  natural next step for public/mobile SMART clients.
