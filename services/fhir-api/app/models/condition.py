"""FHIR R4 Condition resource (subset), validated with Pydantic v2.

Condition.code is where ICD-10 / SNOMED CT coded diagnoses live -- see
``services/analytics/mapping`` for the ICD-10 -> SNOMED CT mapping utility
that operates on this field.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from app.models.common import CodeableConcept, FHIRBaseModel, Identifier, Meta, Reference


class Condition(FHIRBaseModel):
    resourceType: Literal["Condition"] = "Condition"
    id: str | None = None
    meta: Meta | None = None
    identifier: list[Identifier] = Field(default_factory=list)
    clinicalStatus: CodeableConcept | None = None
    verificationStatus: CodeableConcept | None = None
    category: list[CodeableConcept] = Field(default_factory=list)
    severity: CodeableConcept | None = None
    code: CodeableConcept | None = None
    subject: Reference
    encounter: Reference | None = None
    onsetDateTime: datetime | date | None = None
    recordedDate: datetime | date | None = None

    def icd10_codes(self) -> list[str]:
        if not self.code:
            return []
        return [
            c.code
            for c in self.code.coding
            if c.system and "icd-10" in c.system.lower() and c.code
        ]

    def snomed_codes(self) -> list[str]:
        if not self.code:
            return []
        return [
            c.code
            for c in self.code.coding
            if c.system and "snomed" in c.system.lower() and c.code
        ]
