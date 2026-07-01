"""Runtime configuration for the FHIR gateway, loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Upstream HAPI FHIR server that actually stores clinical resources.
    fhir_upstream_url: str = "http://localhost:8080/fhir"

    # Redis is used for both the JWT-based rate limiter and short-lived
    # caching of read-heavy FHIR search responses.
    redis_url: str = "redis://localhost:6379/0"

    # OAuth2 / SMART on FHIR token signing. In production this secret
    # must be injected via a secrets manager, never committed.
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_seconds: int = 3600
    auth_code_expire_seconds: int = 300

    # Public base URL this gateway is served from, advertised in the
    # SMART discovery document.
    issuer_url: str = "http://localhost:8000"

    rate_limit_per_minute: int = 60

    app_name: str = "HealthBridge FHIR Gateway"


settings = Settings()
