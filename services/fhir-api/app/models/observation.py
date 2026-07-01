"""FHIR R4 Observation resource (subset), validated with Pydantic v2."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from app.models.common import CodeableConcept, FHIRBaseModel, Identifier, Meta, Quantity, Reference

ObservationStatus = Literal[
    "registered",
    "preliminary",
    "final",
    "amended",
    "corrected",
    "cancelled",
    "entered-in-error",
    "unknown",
]


class Observation(FHIRBaseModel):
    resourceType: Literal["Observation"] = "Observation"
    id: str | None = None
    meta: Meta | None = None
    identifier: list[Identifier] = Field(default_factory=list)
    status: ObservationStatus
    category: list[CodeableConcept] = Field(default_factory=list)
    code: CodeableConcept
    subject: Reference | None = None
    encounter: Reference | None = None
    effectiveDateTime: datetime | date | None = None
    issued: datetime | None = None
    valueQuantity: Quantity | None = None
    valueString: str | None = None
    valueCodeableConcept: CodeableConcept | None = None
    interpretation: list[CodeableConcept] = Field(default_factory=list)

    @model_validator(mode="after")
    def one_value_type_at_most(self) -> Observation:
        """FHIR invariant obs-6-ish: value[x] is a choice type, not multiple simultaneously."""
        set_values = [
            v
            for v in (self.valueQuantity, self.valueString, self.valueCodeableConcept)
            if v is not None
        ]
        if len(set_values) > 1:
            raise ValueError("Observation may set at most one of valueQuantity/valueString/valueCodeableConcept")
        return self

    def loinc_code(self) -> str | None:
        for coding in self.code.coding:
            if coding.system and "loinc" in coding.system.lower():
                return coding.code
        return None
