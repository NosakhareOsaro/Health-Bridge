"""SMART on FHIR OAuth2 endpoints: discovery, authorization, and token issuance.

Implements the subset of the SMART App Launch v1 spec needed for a
portfolio-grade demonstration:

- ``GET /.well-known/smart-configuration`` -- SMART discovery document
- ``GET /oauth/authorize`` -- authorization_code grant, standalone launch
  (auto-approves consent since there is no real end-user identity store;
  a production IdP would render a login + consent screen here)
- ``POST /oauth/token`` -- exchanges an authorization code, or authenticates
  a backend service via ``client_credentials``, for a signed JWT
"""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import (
    authenticate_client,
    consume_authorization_code,
    get_registered_client,
    issue_access_token,
    register_authorization_code,
)

router = APIRouter(tags=["SMART on FHIR / OAuth2"])


@router.get("/.well-known/smart-configuration")
async def smart_configuration() -> dict:
    """SMART discovery document, as fetched by SMART app launch frameworks."""
    base = settings.issuer_url
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "grant_types_supported": ["authorization_code", "client_credentials"],
        "scopes_supported": [
            "openid",
            "fhirUser",
            "launch",
            "launch/patient",
            "patient/*.read",
            "patient/*.write",
            "system/*.read",
        ],
        "response_types_supported": ["code"],
        "capabilities": [
            "launch-standalone",
            "client-confidential-symmetric",
            "context-standalone-patient",
            "permission-patient",
            "permission-v1",
        ],
        "code_challenge_methods_supported": [],
    }


@router.get("/oauth/authorize")
async def authorize(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str | None = None,
    aud: str | None = None,
    launch: str | None = None,
) -> RedirectResponse:
    if response_type != "code":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported_response_type")

    try:
        client = get_registered_client(client_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    if redirect_uri not in client.redirect_uris:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_redirect_uri")

    requested = set(scope.split())
    granted = requested & client.allowed_scopes
    if not granted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_scope")

    # Standalone launch: the demo "patient in context" is fixed for
    # reproducibility. A real deployment would resolve this from the
    # authenticated end-user's session.
    patient_in_context = "example-patient-1" if "launch/patient" in granted else None

    code = register_authorization_code(
        client_id=client_id,
        scope=" ".join(sorted(granted)),
        redirect_uri=redirect_uri,
        patient=patient_in_context,
    )

    params = f"code={code}"
    if state:
        params += f"&state={state}"
    return RedirectResponse(url=f"{redirect_uri}?{params}", status_code=status.HTTP_302_FOUND)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str
    patient: str | None = None


@router.post("/oauth/token", response_model=TokenResponse)
async def token(
    grant_type: str = Form(...),
    code: str | None = Form(default=None),
    redirect_uri: str | None = Form(default=None),
    client_id: str = Form(...),
    client_secret: str | None = Form(default=None),
    scope: str | None = Form(default=None),
) -> TokenResponse:
    if grant_type == "authorization_code":
        if not code:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing code")
        try:
            auth_code = consume_authorization_code(code)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

        if auth_code.client_id != client_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "client_id mismatch")
        if redirect_uri and auth_code.redirect_uri != redirect_uri:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "redirect_uri mismatch")

        access_token, expires_in = issue_access_token(
            subject=auth_code.patient or client_id,
            scope=auth_code.scope,
            client_id=client_id,
            patient=auth_code.patient,
        )
        return TokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            scope=auth_code.scope,
            patient=auth_code.patient,
        )

    if grant_type == "client_credentials":
        try:
            client = authenticate_client(client_id, client_secret)
        except ValueError as exc:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

        requested = set((scope or "").split()) or client.allowed_scopes
        granted = requested & client.allowed_scopes
        if not granted:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_scope")

        access_token, expires_in = issue_access_token(
            subject=client_id, scope=" ".join(sorted(granted)), client_id=client_id
        )
        return TokenResponse(access_token=access_token, expires_in=expires_in, scope=" ".join(sorted(granted)))

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported_grant_type")
