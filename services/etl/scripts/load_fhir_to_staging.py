#!/usr/bin/env python3
"""Load Synthea-generated FHIR R4 bundles into the OMOP ETL staging schema.

Reads every ``*.json`` FHIR Bundle in ``--input-dir`` (as produced by Synthea's
FHIR exporter), extracts Patient/Encounter/Condition/Observation resources,
and upserts them into the ``staging`` Postgres schema (created/versioned by
Alembic -- see ``services/etl/alembic``) using an async SQLAlchemy engine.

Usage:
    python scripts/load_fhir_to_staging.py --input-dir synthea/output/fhir
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.base import get_engine, get_sessionmaker  # noqa: E402
from models.staging import (  # noqa: E402
    EtlBatch,
    StagingCondition,
    StagingEncounter,
    StagingObservation,
    StagingPatient,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("load_fhir_to_staging")


def strip_reference(reference: str | None) -> str | None:
    """Normalize a FHIR reference (``urn:uuid:...`` or ``Patient/...``) to a bare id."""
    if not reference:
        return None
    for prefix in ("urn:uuid:", "Patient/", "Encounter/"):
        if reference.startswith(prefix):
            return reference[len(prefix) :]
    return reference


def extract_us_core_extension(resource: dict, extension_url_suffix: str) -> str | None:
    """Pull the human-readable display text out of a US Core race/ethnicity extension."""
    for ext in resource.get("extension", []):
        if not ext.get("url", "").endswith(extension_url_suffix):
            continue
        for sub in ext.get("extension", []):
            if sub.get("url") == "ombCategory":
                return sub.get("valueCoding", {}).get("display")
            if sub.get("url") == "text":
                return sub.get("valueString")
    return None


def parse_patient(resource: dict, loaded_at: dt.datetime) -> dict[str, Any]:
    names = resource.get("name", [])
    official = next((n for n in names if n.get("use") == "official"), names[0] if names else {})
    addresses = resource.get("address", [])
    address = addresses[0] if addresses else {}

    death_date = None
    if "deceasedDateTime" in resource:
        death_date = dt.datetime.fromisoformat(resource["deceasedDateTime"]).date()

    return {
        "fhir_id": resource["id"],
        "family_name": official.get("family"),
        "given_name": " ".join(official.get("given", [])) or None,
        "gender": resource.get("gender"),
        "birth_date": dt.date.fromisoformat(resource["birthDate"]) if resource.get("birthDate") else None,
        "death_date": death_date,
        "race": extract_us_core_extension(resource, "us-core-race"),
        "ethnicity": extract_us_core_extension(resource, "us-core-ethnicity"),
        "address_city": address.get("city"),
        "address_state": address.get("state"),
        "address_postal_code": address.get("postalCode"),
        "raw_json": resource,
        "loaded_at": loaded_at,
    }


def parse_encounter(resource: dict, loaded_at: dt.datetime) -> dict[str, Any]:
    period = resource.get("period", {})
    types = resource.get("type", [{}])
    type_coding = (types[0].get("coding") or [{}])[0] if types else {}
    reason = resource.get("reasonCode", [{}])
    reason_coding = (reason[0].get("coding") or [{}])[0] if reason else {}

    return {
        "fhir_id": resource["id"],
        "patient_fhir_id": strip_reference(resource.get("subject", {}).get("reference")),
        "status": resource.get("status"),
        "class_code": resource.get("class", {}).get("code"),
        "type_code": type_coding.get("code"),
        "type_display": type_coding.get("display"),
        "period_start": dt.datetime.fromisoformat(period["start"]) if period.get("start") else None,
        "period_end": dt.datetime.fromisoformat(period["end"]) if period.get("end") else None,
        "reason_code": reason_coding.get("code"),
        "raw_json": resource,
        "loaded_at": loaded_at,
    }


def parse_condition(resource: dict, loaded_at: dt.datetime) -> dict[str, Any]:
    codings = resource.get("code", {}).get("coding", [])
    icd10 = next((c for c in codings if "icd-10" in (c.get("system") or "").lower()), None)
    snomed = next((c for c in codings if "snomed" in (c.get("system") or "").lower()), None)

    onset = resource.get("onsetDateTime")
    recorded = resource.get("recordedDate")

    return {
        "fhir_id": resource["id"],
        "patient_fhir_id": strip_reference(resource.get("subject", {}).get("reference")),
        "encounter_fhir_id": strip_reference(resource.get("encounter", {}).get("reference")),
        "clinical_status": (resource.get("clinicalStatus", {}).get("coding") or [{}])[0].get("code"),
        "icd10_code": icd10.get("code") if icd10 else None,
        "icd10_display": icd10.get("display") if icd10 else None,
        "snomed_code": snomed.get("code") if snomed else None,
        "snomed_display": snomed.get("display") if snomed else None,
        "onset_date": dt.datetime.fromisoformat(onset).date() if onset else None,
        "recorded_date": dt.datetime.fromisoformat(recorded).date() if recorded else None,
        "raw_json": resource,
        "loaded_at": loaded_at,
    }


def parse_observations(resource: dict, loaded_at: dt.datetime) -> list[dict[str, Any]]:
    """Flatten an Observation into one or more staging rows.

    Panel observations (e.g. LOINC 85354-9 "Blood pressure panel") carry no
    top-level value themselves -- their scalar readings live in
    ``component[]``. Each component is emitted as its own staging row so
    downstream OMOP Measurement mapping can treat systolic/diastolic BP the
    same as any other single-valued vital.
    """
    patient_id = strip_reference(resource.get("subject", {}).get("reference"))
    encounter_id = strip_reference(resource.get("encounter", {}).get("reference"))
    effective = resource.get("effectiveDateTime")
    effective_dt = dt.datetime.fromisoformat(effective) if effective else None
    base_id = resource["id"]

    def build_row(fhir_id: str, code_block: dict, value_block: dict) -> dict[str, Any]:
        coding = (code_block.get("coding") or [{}])[0]
        return {
            "fhir_id": fhir_id,
            "patient_fhir_id": patient_id,
            "encounter_fhir_id": encounter_id,
            "status": resource.get("status"),
            "loinc_code": coding.get("code") if "loinc" in (coding.get("system") or "").lower() else None,
            "loinc_display": coding.get("display"),
            "effective_date": effective_dt,
            "value_quantity": value_block.get("valueQuantity", {}).get("value"),
            "value_unit": value_block.get("valueQuantity", {}).get("unit"),
            "value_string": value_block.get("valueString"),
            "raw_json": resource,
            "loaded_at": loaded_at,
        }

    components = resource.get("component")
    if components:
        return [
            build_row(f"{base_id}-component-{i}", c.get("code", {}), c)
            for i, c in enumerate(components)
        ]

    if "valueQuantity" not in resource and "valueString" not in resource:
        return []

    return [build_row(base_id, resource.get("code", {}), resource)]


# A single multi-row INSERT binds len(chunk) * len(columns) parameters. Postgres/asyncpg
# reject statements above 32767 bound parameters, and a patient with a long medical history
# can easily produce several thousand observation rows -- so upserts are chunked.
UPSERT_CHUNK_SIZE = 500


async def upsert_rows(session: AsyncSession, model, rows: list[dict[str, Any]], pk: str) -> int:
    if not rows:
        return 0
    for start in range(0, len(rows), UPSERT_CHUNK_SIZE):
        chunk = rows[start : start + UPSERT_CHUNK_SIZE]
        stmt = pg_insert(model).values(chunk)
        update_cols = {c: getattr(stmt.excluded, c) for c in chunk[0] if c != pk}
        stmt = stmt.on_conflict_do_update(index_elements=[pk], set_=update_cols)
        await session.execute(stmt)
    return len(rows)


async def load_directory(input_dir: Path, database_url: str | None) -> dict[str, int]:
    engine = get_engine(database_url) if database_url else get_engine()
    session_factory = get_sessionmaker(engine)

    loaded_at = dt.datetime.now(dt.UTC)
    counts = {"patients": 0, "encounters": 0, "conditions": 0, "observations": 0}

    bundle_files = sorted(input_dir.glob("*.json"))
    logger.info("Found %d FHIR bundle files in %s", len(bundle_files), input_dir)

    async with session_factory() as session:
        batch = EtlBatch(
            source_system="synthea",
            source_path=str(input_dir),
            started_at=loaded_at,
            record_counts={},
        )
        session.add(batch)
        await session.flush()

        for path in bundle_files:
            bundle = json.loads(path.read_text())
            patients, encounters, conditions, observations = [], [], [], []

            for entry in bundle.get("entry", []):
                resource = entry.get("resource", {})
                rtype = resource.get("resourceType")
                if rtype == "Patient":
                    patients.append(parse_patient(resource, loaded_at))
                elif rtype == "Encounter":
                    encounters.append(parse_encounter(resource, loaded_at))
                elif rtype == "Condition":
                    conditions.append(parse_condition(resource, loaded_at))
                elif rtype == "Observation":
                    observations.extend(parse_observations(resource, loaded_at))

            # Patients first (FK target), then encounters, then conditions/observations.
            counts["patients"] += await upsert_rows(session, StagingPatient, patients, "fhir_id")
            await session.flush()
            counts["encounters"] += await upsert_rows(session, StagingEncounter, encounters, "fhir_id")
            await session.flush()
            counts["conditions"] += await upsert_rows(session, StagingCondition, conditions, "fhir_id")
            counts["observations"] += await upsert_rows(session, StagingObservation, observations, "fhir_id")

        batch.finished_at = dt.datetime.now(dt.UTC)
        batch.record_counts = counts
        await session.commit()

    await engine.dispose()
    return counts


async def _verify_load(database_url: str | None) -> None:
    engine = get_engine(database_url) if database_url else get_engine()
    session_factory = get_sessionmaker(engine)
    async with session_factory() as session:
        for model, label in [
            (StagingPatient, "patients"),
            (StagingEncounter, "encounters"),
            (StagingCondition, "conditions"),
            (StagingObservation, "observations"),
        ]:
            result = await session.execute(select(model))
            logger.info("staging.%s row count: %d", label, len(result.scalars().all()))
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "synthea" / "output" / "fhir",
        help="Directory of Synthea FHIR bundle *.json files",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="postgresql+asyncpg://... override (default: OMOP_DB_ASYNC_URL env var)",
    )
    args = parser.parse_args()

    if not args.input_dir.exists():
        raise SystemExit(
            f"Input directory {args.input_dir} does not exist. "
            "Run scripts/generate_synthea.sh first."
        )

    counts = asyncio.run(load_directory(args.input_dir, args.database_url))
    logger.info("Load complete: %s", counts)


if __name__ == "__main__":
    main()
