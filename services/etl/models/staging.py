"""Staging-layer tables: a flattened, typed landing zone for extracted FHIR resources.

These tables are intentionally close to the FHIR shape (not yet OMOP-shaped)
-- the Python loader (``scripts/load_fhir_to_staging.py``) writes here, and
the dbt project reads these as ``source()`` tables when building the OMOP CDM.
Schema versioning for this layer is handled by Alembic (see
``services/etl/alembic``).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base

STAGING_SCHEMA = "staging"


class StagingPatient(Base):
    __tablename__ = "patients"
    __table_args__ = {"schema": STAGING_SCHEMA}

    fhir_id: Mapped[str] = mapped_column(String, primary_key=True)
    family_name: Mapped[str | None] = mapped_column(String)
    given_name: Mapped[str | None] = mapped_column(String)
    gender: Mapped[str | None] = mapped_column(String)
    birth_date: Mapped[dt.date | None] = mapped_column(Date)
    death_date: Mapped[dt.date | None] = mapped_column(Date)
    race: Mapped[str | None] = mapped_column(String)
    ethnicity: Mapped[str | None] = mapped_column(String)
    address_city: Mapped[str | None] = mapped_column(String)
    address_state: Mapped[str | None] = mapped_column(String)
    address_postal_code: Mapped[str | None] = mapped_column(String)
    raw_json: Mapped[dict] = mapped_column(JSON)
    loaded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class StagingEncounter(Base):
    __tablename__ = "encounters"
    __table_args__ = {"schema": STAGING_SCHEMA}

    fhir_id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_fhir_id: Mapped[str] = mapped_column(
        String, ForeignKey(f"{STAGING_SCHEMA}.patients.fhir_id")
    )
    status: Mapped[str | None] = mapped_column(String)
    class_code: Mapped[str | None] = mapped_column(String)
    type_code: Mapped[str | None] = mapped_column(String)
    type_display: Mapped[str | None] = mapped_column(String)
    period_start: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    reason_code: Mapped[str | None] = mapped_column(String)
    raw_json: Mapped[dict] = mapped_column(JSON)
    loaded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class StagingCondition(Base):
    __tablename__ = "conditions"
    __table_args__ = {"schema": STAGING_SCHEMA}

    fhir_id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_fhir_id: Mapped[str] = mapped_column(
        String, ForeignKey(f"{STAGING_SCHEMA}.patients.fhir_id")
    )
    encounter_fhir_id: Mapped[str | None] = mapped_column(String)
    clinical_status: Mapped[str | None] = mapped_column(String)
    icd10_code: Mapped[str | None] = mapped_column(String)
    icd10_display: Mapped[str | None] = mapped_column(Text)
    snomed_code: Mapped[str | None] = mapped_column(String)
    snomed_display: Mapped[str | None] = mapped_column(Text)
    onset_date: Mapped[dt.date | None] = mapped_column(Date)
    recorded_date: Mapped[dt.date | None] = mapped_column(Date)
    raw_json: Mapped[dict] = mapped_column(JSON)
    loaded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class StagingObservation(Base):
    __tablename__ = "observations"
    __table_args__ = {"schema": STAGING_SCHEMA}

    fhir_id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_fhir_id: Mapped[str] = mapped_column(
        String, ForeignKey(f"{STAGING_SCHEMA}.patients.fhir_id")
    )
    encounter_fhir_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    loinc_code: Mapped[str | None] = mapped_column(String)
    loinc_display: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    value_quantity: Mapped[float | None] = mapped_column(Numeric)
    value_unit: Mapped[str | None] = mapped_column(String)
    value_string: Mapped[str | None] = mapped_column(Text)
    raw_json: Mapped[dict] = mapped_column(JSON)
    loaded_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class EtlBatch(Base):
    """Audit trail of ETL runs -- what source, when, and how many rows landed."""

    __tablename__ = "etl_batches"
    __table_args__ = {"schema": STAGING_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String)
    source_path: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    record_counts: Mapped[dict] = mapped_column(JSON, default=dict)
