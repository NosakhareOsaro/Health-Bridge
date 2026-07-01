"""SMART on FHIR OAuth2 support: token issuance, verification and scope enforcement.

This implements a minimal-but-real SMART on FHIR v1 authorization server:

- ``authorization_code`` grant for user-facing SMART app launches
- ``client_credentials`` grant for SMART Backend Services (system-to-system)
- SMART-style scope strings, e.g. ``patient/Observation.read``,
  ``system/*.read``, ``launch/patient``
- JWT access tokens signed with HS256 via Authlib's ``jose`` module

The client and authorization-code registries are in-memory, which is
appropriate for a demo/portfolio deployment. A production system would
back these with a persistent, encrypted store.
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass

from authlib.jose import JoseError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class RegisteredClient:
    client_id: str
    client_secret: str | None
    redirect_uris: list[str]
    allowed_scopes: set[str]
    confidential: bool = True


@dataclass
class AuthorizationCode:
    code: str
    client_id: str
    scope: str
    redirect_uri: str
    patient: str | None
    expires_at: float
    used: bool = False


@dataclass
class TokenData:
    sub: str
    scope: str
    patient: str | None = None
    client_id: str | None = None

    def scopes(self) -> list[str]:
        return self.scope.split() if self.scope else []


# ---------------------------------------------------------------------------
# In-memory registries (demo-grade; swap for a DB-backed store in production)
# ---------------------------------------------------------------------------

CLIENT_REGISTRY: dict[str, RegisteredClient] = {
    "healthbridge-demo-app": RegisteredClient(
        client_id="healthbridge-demo-app",
        client_secret="demo-secret",
        redirect_uris=["http://localhost:8501/callback", "https://example.org/callback"],
        allowed_scopes={
            "patient/Patient.read",
            "patient/Observation.read",
            "patient/Condition.read",
            "patient/Encounter.read",
            "launch/patient",
            "openid",
            "fhirUser",
        },
    ),
    "healthbridge-analytics-service": RegisteredClient(
        client_id="healthbridge-analytics-service",
        client_secret="analytics-secret",
        redirect_uris=[],
        allowed_scopes={"system/*.read"},
        confidential=True,
    ),
}

_AUTH_CODES: dict[str, AuthorizationCode] = {}


def register_authorization_code(
    client_id: str, scope: str, redirect_uri: str, patient: str | None = None
) -> str:
    code = secrets.token_urlsafe(32)
    _AUTH_CODES[code] = AuthorizationCode(
        code=code,
        client_id=client_id,
        scope=scope,
        redirect_uri=redirect_uri,
        patient=patient,
        expires_at=time.time() + settings.auth_code_expire_seconds,
    )
    return code


def consume_authorization_code(code: str) -> AuthorizationCode:
    entry = _AUTH_CODES.get(code)
    if entry is None:
        raise ValueError("invalid_grant: unknown authorization code")
    if entry.used:
        raise ValueError("invalid_grant: authorization code already used")
    if entry.expires_at < time.time():
        raise ValueError("invalid_grant: authorization code expired")
    entry.used = True
    return entry


def get_registered_client(client_id: str) -> RegisteredClient:
    """Look up a client without authenticating it -- used at the /authorize step.

    Per OAuth2/SMART, the client secret is verified at the *token* endpoint,
    not at the authorization endpoint (the redirect happens in the resource
    owner's user agent, where a confidential secret must never appear).
    """
    client = CLIENT_REGISTRY.get(client_id)
    if client is None:
        raise ValueError("invalid_client: unknown client_id")
    return client


def authenticate_client(client_id: str, client_secret: str | None) -> RegisteredClient:
    client = get_registered_client(client_id)
    if client.confidential and client.client_secret != client_secret:
        raise ValueError("invalid_client: bad client_secret")
    return client


# ---------------------------------------------------------------------------
# JWT issuance / verification
# ---------------------------------------------------------------------------

_JWT_HEADER = {"alg": settings.jwt_algorithm}


def issue_access_token(
    subject: str, scope: str, client_id: str, patient: str | None = None
) -> tuple[str, int]:
    now = int(time.time())
    expires_in = settings.access_token_expire_seconds
    payload = {
        "iss": settings.issuer_url,
        "sub": subject,
        "aud": settings.issuer_url,
        "client_id": client_id,
        "scope": scope,
        "iat": now,
        "exp": now + expires_in,
        "jti": str(uuid.uuid4()),
    }
    if patient:
        payload["patient"] = patient
    token = jwt.encode(_JWT_HEADER, payload, settings.jwt_secret_key)
    return token.decode("utf-8") if isinstance(token, bytes) else token, expires_in


def decode_access_token(token: str) -> TokenData:
    try:
        claims = jwt.decode(token, settings.jwt_secret_key)
        claims.validate()
    except JoseError as exc:
        raise ValueError(f"invalid_token: {exc}") from exc

    if claims.get("exp", 0) < time.time():
        raise ValueError("invalid_token: expired")

    return TokenData(
        sub=claims["sub"],
        scope=claims.get("scope", ""),
        patient=claims.get("patient"),
        client_id=claims.get("client_id"),
    )


# ---------------------------------------------------------------------------
# SMART scope matching
# ---------------------------------------------------------------------------


def scope_permits(granted_scopes: list[str], resource_type: str, interaction: str) -> bool:
    """Check whether any granted SMART scope authorizes an interaction on a resource type.

    Supports the SMART v1 scope grammar: ``<context>/<resource>.<permission>``
    where ``<context>`` is ``patient`` or ``system``, ``<resource>`` may be
    ``*`` for all resource types, and ``<permission>`` is one of
    ``read``, ``write``, ``*`` (both).
    """
    interaction_aliases = {"read": {"read", "*"}, "write": {"write", "*"}}
    allowed_perms = interaction_aliases.get(interaction, {interaction, "*"})

    for raw in granted_scopes:
        if "/" not in raw or "." not in raw:
            continue
        _context, rest = raw.split("/", 1)
        res, _, perm = rest.partition(".")
        if res in (resource_type, "*") and perm in allowed_perms:
            return True
    return False


async def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> TokenData:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_scope(resource_type: str, interaction: str = "read"):
    """FastAPI dependency factory enforcing a SMART scope for a resource/interaction pair."""

    async def _checker(token: TokenData = Depends(get_current_token)) -> TokenData:
        if not scope_permits(token.scopes(), resource_type, interaction):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient scope: token grants '{token.scope}', "
                    f"needs {resource_type}.{interaction}"
                ),
            )
        return token

    return _checker
