"""FHIR R4 MolecularSequence resource (subset), validated with Pydantic v2.

Included to demonstrate genomics-adjacent FHIR modeling (e.g. for precision
medicine use cases) alongside the core clinical resources. Structurally
faithful to R4 but scoped to the fields most commonly populated by
variant-calling pipelines.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.models.common import CodeableConcept, FHIRBaseModel, Identifier, Meta, Reference

SequenceType = Literal["aa", "dna", "rna"]


class ReferenceSeq(FHIRBaseModel):
    chromosome: CodeableConcept | None = None
    genomeBuild: str | None = None
    referenceSeqId: CodeableConcept | None = None
    windowStart: int | None = None
    windowEnd: int | None = None


class Variant(FHIRBaseModel):
    start: int | None = None
    end: int | None = None
    observedAllele: str | None = None
    referenceAllele: str | None = None


class Quality(FHIRBaseModel):
    type: Literal["indel", "snp", "unknown"] | None = None
    score: float | None = None
    method: CodeableConcept | None = None


class MolecularSequence(FHIRBaseModel):
    resourceType: Literal["MolecularSequence"] = "MolecularSequence"
    id: str | None = None
    meta: Meta | None = None
    identifier: list[Identifier] = Field(default_factory=list)
    type: SequenceType | None = None
    patient: Reference | None = None
    specimen: Reference | None = None
    referenceSeq: ReferenceSeq | None = None
    variant: list[Variant] = Field(default_factory=list)
    quality: list[Quality] = Field(default_factory=list)
    readCoverage: int | None = None
