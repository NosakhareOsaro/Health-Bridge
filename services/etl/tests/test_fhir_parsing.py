"""Unit tests for the pure FHIR-parsing helpers in scripts/load_fhir_to_staging.py.

These cover the parsing/flattening logic without touching a real database --
the end-to-end load (staging -> Postgres -> dbt -> OMOP CDM) is exercised
manually against a live docker-compose stack, documented in the service
README, since it needs a running Postgres instance.
"""

from __future__ import annotations

import datetime as dt

from scripts.load_fhir_to_staging import (
    extract_us_core_extension,
    parse_condition,
    parse_encounter,
    parse_observations,
    parse_patient,
    strip_reference,
)

LOADED_AT = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def test_strip_reference_handles_all_prefixes():
    assert strip_reference("urn:uuid:abc-123") == "abc-123"
    assert strip_reference("Patient/abc-123") == "abc-123"
    assert strip_reference("Encounter/abc-123") == "abc-123"
    assert strip_reference(None) is None
    assert strip_reference("abc-123") == "abc-123"


def test_extract_us_core_race_extension():
    resource = {
        "extension": [
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                "extension": [
                    {"url": "ombCategory", "valueCoding": {"code": "2106-3", "display": "White"}},
                    {"url": "text", "valueString": "White"},
                ],
            }
        ]
    }
    assert extract_us_core_extension(resource, "us-core-race") == "White"
    assert extract_us_core_extension(resource, "us-core-ethnicity") is None


def test_parse_patient_extracts_demographics_and_death_date():
    resource = {
        "resourceType": "Patient",
        "id": "pat-1",
        "name": [{"use": "official", "family": "Osaro", "given": ["Nosa"]}],
        "gender": "male",
        "birthDate": "1990-05-01",
        "deceasedDateTime": "2020-01-15T10:00:00+01:00",
        "address": [{"city": "Boston", "state": "MA", "postalCode": "02118"}],
        "extension": [
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                "extension": [{"url": "text", "valueString": "White"}],
            },
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity",
                "extension": [{"url": "text", "valueString": "Not Hispanic or Latino"}],
            },
        ],
    }
    row = parse_patient(resource, LOADED_AT)
    assert row["fhir_id"] == "pat-1"
    assert row["family_name"] == "Osaro"
    assert row["given_name"] == "Nosa"
    assert row["birth_date"] == dt.date(1990, 5, 1)
    assert row["death_date"] == dt.date(2020, 1, 15)
    assert row["race"] == "White"
    assert row["ethnicity"] == "Not Hispanic or Latino"
    assert row["address_state"] == "MA"


def test_parse_patient_without_death_date():
    resource = {"resourceType": "Patient", "id": "pat-2", "gender": "female"}
    row = parse_patient(resource, LOADED_AT)
    assert row["death_date"] is None


def test_parse_encounter_extracts_class_and_period():
    resource = {
        "resourceType": "Encounter",
        "id": "enc-1",
        "status": "finished",
        "class": {"code": "AMB"},
        "subject": {"reference": "urn:uuid:pat-1"},
        "period": {"start": "2026-01-01T10:00:00+00:00", "end": "2026-01-01T11:00:00+00:00"},
    }
    row = parse_encounter(resource, LOADED_AT)
    assert row["patient_fhir_id"] == "pat-1"
    assert row["class_code"] == "AMB"
    assert row["period_start"] == dt.datetime(2026, 1, 1, 10, tzinfo=dt.UTC)


def test_parse_condition_prefers_snomed_and_extracts_icd10_separately():
    resource = {
        "resourceType": "Condition",
        "id": "cond-1",
        "subject": {"reference": "urn:uuid:pat-1"},
        "encounter": {"reference": "urn:uuid:enc-1"},
        "clinicalStatus": {"coding": [{"code": "active"}]},
        "code": {
            "coding": [
                {"system": "http://hl7.org/fhir/sid/icd-10", "code": "E11.9"},
                {"system": "http://snomed.info/sct", "code": "44054006", "display": "Diabetes"},
            ]
        },
        "recordedDate": "2020-01-15T10:00:00+01:00",
    }
    row = parse_condition(resource, LOADED_AT)
    assert row["icd10_code"] == "E11.9"
    assert row["snomed_code"] == "44054006"
    assert row["snomed_display"] == "Diabetes"
    assert row["recorded_date"] == dt.date(2020, 1, 15)


def test_parse_observations_splits_panel_components():
    resource = {
        "resourceType": "Observation",
        "id": "obs-1",
        "status": "final",
        "subject": {"reference": "urn:uuid:pat-1"},
        "code": {"coding": [{"system": "http://loinc.org", "code": "85354-9"}]},
        "effectiveDateTime": "2026-01-15T10:00:00+00:00",
        "component": [
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
                "valueQuantity": {"value": 130, "unit": "mm[Hg]"},
            },
            {
                "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4"}]},
                "valueQuantity": {"value": 75, "unit": "mm[Hg]"},
            },
        ],
    }
    rows = parse_observations(resource, LOADED_AT)
    assert len(rows) == 2
    assert rows[0]["fhir_id"] == "obs-1-component-0"
    assert rows[0]["loinc_code"] == "8480-6"
    assert rows[0]["value_quantity"] == 130
    assert rows[1]["loinc_code"] == "8462-4"


def test_parse_observations_simple_scalar_value():
    resource = {
        "resourceType": "Observation",
        "id": "obs-2",
        "status": "final",
        "subject": {"reference": "urn:uuid:pat-1"},
        "code": {"coding": [{"system": "http://loinc.org", "code": "8302-2"}]},
        "effectiveDateTime": "2026-01-15T10:00:00+00:00",
        "valueQuantity": {"value": 180, "unit": "cm"},
    }
    rows = parse_observations(resource, LOADED_AT)
    assert len(rows) == 1
    assert rows[0]["value_quantity"] == 180


def test_parse_observations_skips_valueless_non_panel_observation():
    resource = {
        "resourceType": "Observation",
        "id": "obs-3",
        "status": "final",
        "subject": {"reference": "urn:uuid:pat-1"},
        "code": {"coding": [{"system": "http://loinc.org", "code": "1234-5"}]},
    }
    assert parse_observations(resource, LOADED_AT) == []
