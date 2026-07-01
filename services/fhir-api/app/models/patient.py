"""FHIR R4 Patient resource (subset), validated with Pydantic v2."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, field_validator

from app.models.common import (
    Address,
    ContactPoint,
    FHIRBaseModel,
    HumanName,
    Identifier,
    Meta,
)


class Patient(FHIRBaseModel):
    resourceType: Literal["Patient"] = "Patient"
    id: str | None = None
    meta: Meta | None = None
    identifier: list[Identifier] = Field(default_factory=list)
    active: bool | None = True
    name: list[HumanName] = Field(default_factory=list)
    telecom: list[ContactPoint] = Field(default_factory=list)
    gender: Literal["male", "female", "other", "unknown"] | None = None
    birthDate: date | None = None
    deceasedBoolean: bool | None = None
    address: list[Address] = Field(default_factory=list)
    maritalStatus: dict | None = None

    @field_validator("birthDate")
    @classmethod
    def birth_date_not_in_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("Patient.birthDate cannot be in the future")
        return value

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name[0].full_name
        return self.id or "unknown"
