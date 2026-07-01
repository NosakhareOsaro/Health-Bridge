"""create staging schema and tables

Revision ID: 0001
Revises:
Create Date: 2026-07-01
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS staging")

    op.create_table(
        "patients",
        sa.Column("fhir_id", sa.String(), primary_key=True),
        sa.Column("family_name", sa.String()),
        sa.Column("given_name", sa.String()),
        sa.Column("gender", sa.String()),
        sa.Column("birth_date", sa.Date()),
        sa.Column("death_date", sa.Date()),
        sa.Column("race", sa.String()),
        sa.Column("ethnicity", sa.String()),
        sa.Column("address_city", sa.String()),
        sa.Column("address_state", sa.String()),
        sa.Column("address_postal_code", sa.String()),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        schema="staging",
    )

    op.create_table(
        "encounters",
        sa.Column("fhir_id", sa.String(), primary_key=True),
        sa.Column(
            "patient_fhir_id",
            sa.String(),
            sa.ForeignKey("staging.patients.fhir_id"),
            nullable=False,
        ),
        sa.Column("status", sa.String()),
        sa.Column("class_code", sa.String()),
        sa.Column("type_code", sa.String()),
        sa.Column("type_display", sa.String()),
        sa.Column("period_start", sa.DateTime(timezone=True)),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("reason_code", sa.String()),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        schema="staging",
    )

    op.create_table(
        "conditions",
        sa.Column("fhir_id", sa.String(), primary_key=True),
        sa.Column(
            "patient_fhir_id",
            sa.String(),
            sa.ForeignKey("staging.patients.fhir_id"),
            nullable=False,
        ),
        sa.Column("encounter_fhir_id", sa.String()),
        sa.Column("clinical_status", sa.String()),
        sa.Column("icd10_code", sa.String()),
        sa.Column("icd10_display", sa.Text()),
        sa.Column("snomed_code", sa.String()),
        sa.Column("snomed_display", sa.Text()),
        sa.Column("onset_date", sa.Date()),
        sa.Column("recorded_date", sa.Date()),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        schema="staging",
    )

    op.create_table(
        "observations",
        sa.Column("fhir_id", sa.String(), primary_key=True),
        sa.Column(
            "patient_fhir_id",
            sa.String(),
            sa.ForeignKey("staging.patients.fhir_id"),
            nullable=False,
        ),
        sa.Column("encounter_fhir_id", sa.String()),
        sa.Column("status", sa.String()),
        sa.Column("loinc_code", sa.String()),
        sa.Column("loinc_display", sa.Text()),
        sa.Column("effective_date", sa.DateTime(timezone=True)),
        sa.Column("value_quantity", sa.Numeric()),
        sa.Column("value_unit", sa.String()),
        sa.Column("value_string", sa.Text()),
        sa.Column("raw_json", sa.JSON(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        schema="staging",
    )

    op.create_table(
        "etl_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_system", sa.String(), nullable=False),
        sa.Column("source_path", sa.String()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("record_counts", sa.JSON(), nullable=False),
        schema="staging",
    )

    op.create_index(
        "ix_staging_encounters_patient", "encounters", ["patient_fhir_id"], schema="staging"
    )
    op.create_index(
        "ix_staging_conditions_patient", "conditions", ["patient_fhir_id"], schema="staging"
    )
    op.create_index(
        "ix_staging_conditions_icd10", "conditions", ["icd10_code"], schema="staging"
    )
    op.create_index(
        "ix_staging_observations_patient", "observations", ["patient_fhir_id"], schema="staging"
    )
    op.create_index(
        "ix_staging_observations_loinc", "observations", ["loinc_code"], schema="staging"
    )


def downgrade() -> None:
    # Note: deliberately does not DROP SCHEMA staging -- Alembic's own
    # version table (staging.alembic_version) lives in this schema, and
    # dropping the schema here would destroy it before Alembic finishes
    # recording the downgrade.
    op.drop_table("etl_batches", schema="staging")
    op.drop_table("observations", schema="staging")
    op.drop_table("conditions", schema="staging")
    op.drop_table("encounters", schema="staging")
    op.drop_table("patients", schema="staging")
