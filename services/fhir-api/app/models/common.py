"""Shared FHIR R4 datatypes used across resource models.

These are intentionally a *subset* of the full FHIR datatype specification --
enough to model realistic Patient/Encounter/Condition/Observation/
MolecularSequence payloads with real validation, without reimplementing the
entire FHIR type system.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FHIRBaseModel(BaseModel):
    """Base for all FHIR datatypes: tolerant of extra vendor fields, FHIR uses camelCase."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class Meta(FHIRBaseModel):
    versionId: str | None = None
    lastUpdated: datetime | None = None
    profile: list[str] = Field(default_factory=list)


class Coding(FHIRBaseModel):
    system: str | None = None
    version: str | None = None
    code: str | None = None
    display: str | None = None
    userSelected: bool | None = None


class CodeableConcept(FHIRBaseModel):
    coding: list[Coding] = Field(default_factory=list)
    text: str | None = None


class Identifier(FHIRBaseModel):
    use: Literal["usual", "official", "temp", "secondary", "old"] | None = None
    system: str | None = None
    value: str | None = None


class HumanName(FHIRBaseModel):
    use: Literal["usual", "official", "temp", "nickname", "anonymous", "old", "maiden"] | None = (
        None
    )
    family: str | None = None
    given: list[str] = Field(default_factory=list)
    text: str | None = None

    @property
    def full_name(self) -> str:
        parts = [*self.given, self.family] if self.family else list(self.given)
        return " ".join(p for p in parts if p) or (self.text or "")


class ContactPoint(FHIRBaseModel):
    system: Literal["phone", "fax", "email", "pager", "url", "sms", "other"] | None = None
    value: str | None = None
    use: Literal["home", "work", "temp", "old", "mobile"] | None = None


class Address(FHIRBaseModel):
    use: Literal["home", "work", "temp", "old", "billing"] | None = None
    line: list[str] = Field(default_factory=list)
    city: str | None = None
    state: str | None = None
    postalCode: str | None = None
    country: str | None = None


class Period(FHIRBaseModel):
    start: datetime | None = None
    end: datetime | None = None


class Reference(FHIRBaseModel):
    reference: str | None = None
    type: str | None = None
    display: str | None = None

    def resource_type(self) -> str | None:
        if self.reference and "/" in self.reference:
            return self.reference.split("/", 1)[0]
        return self.type

    def resource_id(self) -> str | None:
        if self.reference and "/" in self.reference:
            return self.reference.split("/", 1)[1]
        return None


class Quantity(FHIRBaseModel):
    value: float | None = None
    unit: str | None = None
    system: str | None = None
    code: str | None = None


class Annotation(FHIRBaseModel):
    text: str
    time: datetime | None = None


__all__ = [
    "Address",
    "Annotation",
    "CodeableConcept",
    "Coding",
    "ContactPoint",
    "FHIRBaseModel",
    "HumanName",
    "Identifier",
    "Meta",
    "Period",
    "Quantity",
    "Reference",
]
