"""Unit tests for FHIR Pydantic v2 model validation and helper methods."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.models.condition import Condition
from app.models.encounter import Encounter
from app.models.molecular_sequence import MolecularSequence
from app.models.patient import Patient


def test_patient_rejects_future_birthdate():
    with pytest.raises(ValidationError):
        Patient.model_validate({"birthDate": (date.today() + timedelta(days=1)).isoformat()})


def test_patient_display_name_prefers_official_name():
    patient = Patient.model_validate(
        {"name": [{"family": "Osaro", "given": ["Nosa", "K"]}]}
    )
    assert patient.display_name == "Nosa K Osaro"


def test_encounter_length_of_stay_hours():
    encounter = Encounter.model_validate(
        {
            "status": "finished",
            "class": {"code": "EMER", "display": "emergency"},
            "period": {"start": "2026-01-01T10:00:00Z", "end": "2026-01-01T14:30:00Z"},
        }
    )
    assert encounter.length_of_stay_hours() == 4.5


def test_encounter_requires_status():
    with pytest.raises(ValidationError):
        Encounter.model_validate({"class": {"code": "EMER"}})


def test_condition_extracts_icd10_and_snomed_codes():
    condition = Condition.model_validate(
        {
            "subject": {"reference": "Patient/example-patient-1"},
            "code": {
                "coding": [
                    {"system": "http://hl7.org/fhir/sid/icd-10", "code": "E11.9"},
                    {"system": "http://snomed.info/sct", "code": "44054006"},
                ]
            },
        }
    )
    assert condition.icd10_codes() == ["E11.9"]
    assert condition.snomed_codes() == ["44054006"]


def test_molecular_sequence_variant_roundtrip():
    seq = MolecularSequence.model_validate(
        {
            "type": "dna",
            "patient": {"reference": "Patient/example-patient-1"},
            "referenceSeq": {"genomeBuild": "GRCh38", "windowStart": 100, "windowEnd": 200},
            "variant": [{"start": 150, "end": 151, "observedAllele": "A", "referenceAllele": "G"}],
        }
    )
    assert seq.referenceSeq.genomeBuild == "GRCh38"
    assert seq.variant[0].observedAllele == "A"
