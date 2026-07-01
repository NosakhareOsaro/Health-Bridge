"""Async HTTP client wrapping the upstream HAPI FHIR R4 server.

The FastAPI gateway does not persist clinical data itself -- HAPI FHIR is
the system of record. This module centralizes all upstream calls (search,
read, create) so routers stay thin and so tests can mock a single seam
with ``respx`` instead of stubbing every router individually.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class FHIRClientError(RuntimeError):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(f"Upstream FHIR error {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class FHIRClient:
    """Thin async wrapper around the HAPI FHIR REST API."""

    def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None):
        self.base_url = (base_url or settings.fhir_upstream_url).rstrip("/")
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Accept": "application/fhir+json", "Content-Type": "application/fhir+json"},
            timeout=10.0,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def read(self, resource_type: str, resource_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"/{resource_type}/{resource_id}")
        self._raise_for_status(resp)
        return resp.json()

    async def search(self, resource_type: str, params: dict[str, Any]) -> dict[str, Any]:
        clean_params = {k: v for k, v in params.items() if v is not None}
        resp = await self._client.get(f"/{resource_type}", params=clean_params)
        self._raise_for_status(resp)
        return resp.json()

    async def create(self, resource_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        resp = await self._client.post(f"/{resource_type}", json=payload)
        self._raise_for_status(resp)
        return resp.json()

    async def capabilities(self) -> dict[str, Any]:
        resp = await self._client.get("/metadata")
        self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            raise FHIRClientError(resp.status_code, detail)


_default_client: FHIRClient | None = None


def get_fhir_client() -> FHIRClient:
    global _default_client
    if _default_client is None:
        _default_client = FHIRClient()
    return _default_client


def set_fhir_client(client: FHIRClient) -> None:
    """Test hook to inject a client pointed at a mocked transport."""
    global _default_client
    _default_client = client
