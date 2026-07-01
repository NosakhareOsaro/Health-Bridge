"""Generic FHIR searchset Bundle wrapper used for all resource search responses."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from app.models.common import FHIRBaseModel


class BundleLink(FHIRBaseModel):
    relation: str
    url: str


class BundleEntry(FHIRBaseModel):
    fullUrl: str | None = None
    resource: dict[str, Any] | None = None
    search: dict[str, Any] | None = None


class Bundle(FHIRBaseModel):
    resourceType: Literal["Bundle"] = "Bundle"
    type: str = "searchset"
    total: int | None = None
    link: list[BundleLink] = Field(default_factory=list)
    entry: list[BundleEntry] = Field(default_factory=list)

    @classmethod
    def from_fhir_json(cls, raw: dict[str, Any]) -> Bundle:
        return cls.model_validate(raw)

    def resources(self) -> list[dict[str, Any]]:
        return [e.resource for e in self.entry if e.resource is not None]
