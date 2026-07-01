"""FHIR R4 Encounter resource (subset), validated with Pydantic v2."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.common import (
    CodeableConcept,
    Coding,
    FHIRBaseModel,
    Identifier,
    Meta,
    Period,
    Reference,
)

EncounterStatus = Literal[
    "planned",
    "arrived",
    "triaged",
    "in-progress",
    "onleave",
    "finished",
    "cancelled",
    "entered-in-error",
    "unknown",
]


class Encounter(FHIRBaseModel):
    resourceType: Literal["Encounter"] = "Encounter"
    id: str | None = None
    meta: Meta | None = None
    identifier: list[Identifier] = Field(default_factory=list)
    status: EncounterStatus
    class_: Coding | None = Field(default=None, alias="class")
    type: list[CodeableConcept] = Field(default_factory=list)
    subject: Reference | None = None
    period: Period | None = None
    reasonCode: list[CodeableConcept] = Field(default_factory=list)
    serviceProvider: Reference | None = None

    def length_of_stay_hours(self) -> float | None:
        """Compute LOS in hours from period.start/end, used by the analytics service."""
        if self.period and self.period.start and self.period.end:
            delta = self.period.end - self.period.start
            return round(delta.total_seconds() / 3600, 2)
        return None
