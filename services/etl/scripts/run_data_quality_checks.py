#!/usr/bin/env python3
"""Great Expectations data-quality suite for the OMOP CDM tables.

Builds (or reuses) a file-backed Great Expectations project under
``services/etl/great_expectations``, defines expectation suites for the core
CDM tables produced by the dbt project, runs them as a checkpoint, renders
Data Docs, and exits non-zero if any expectation fails (so this can gate CI).

Usage:
    python scripts/run_data_quality_checks.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import great_expectations as gx
from great_expectations.core.batch import BatchRequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent / "great_expectations"
DATASOURCE_NAME = "omop_cdm"

DB_URL = os.environ.get(
    "OMOP_DB_SYNC_URL", "postgresql+psycopg2://omop:omop@localhost:5434/omop"
)


def build_person_suite(validator) -> None:
    validator.expect_column_values_to_not_be_null("person_id")
    validator.expect_column_values_to_be_unique("person_id")
    validator.expect_column_values_to_be_in_set("gender_concept_id", [8507, 8532, 8551])
    validator.expect_column_values_to_not_be_null("race_concept_id")
    validator.expect_column_values_to_not_be_null("ethnicity_concept_id")
    validator.expect_column_values_to_be_between("year_of_birth", min_value=1900, max_value=2026)
    validator.save_expectation_suite(discard_failed_expectations=False)


def build_visit_occurrence_suite(validator) -> None:
    validator.expect_column_values_to_not_be_null("visit_occurrence_id")
    validator.expect_column_values_to_be_unique("visit_occurrence_id")
    validator.expect_column_values_to_not_be_null("person_id")
    validator.expect_column_values_to_not_be_null("visit_start_date")
    validator.expect_column_pair_values_a_to_be_greater_than_b(
        column_A="visit_end_date", column_B="visit_start_date", or_equal=True
    )
    validator.save_expectation_suite(discard_failed_expectations=False)


def build_condition_occurrence_suite(validator) -> None:
    validator.expect_column_values_to_not_be_null("condition_occurrence_id")
    validator.expect_column_values_to_be_unique("condition_occurrence_id")
    validator.expect_column_values_to_not_be_null("person_id")
    validator.expect_column_values_to_not_be_null("condition_concept_id")
    validator.expect_column_values_to_not_be_null("condition_start_date")
    validator.save_expectation_suite(discard_failed_expectations=False)


def build_measurement_suite(validator) -> None:
    validator.expect_column_values_to_not_be_null("measurement_id")
    validator.expect_column_values_to_be_unique("measurement_id")
    validator.expect_column_values_to_not_be_null("person_id")
    validator.expect_column_values_to_not_be_null("value_as_number")
    validator.save_expectation_suite(discard_failed_expectations=False)


TABLE_SUITES = {
    "person": build_person_suite,
    "visit_occurrence": build_visit_occurrence_suite,
    "condition_occurrence": build_condition_occurrence_suite,
    "measurement": build_measurement_suite,
}


def main() -> int:
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    context = gx.get_context(mode="file", project_root_dir=str(PROJECT_ROOT))

    datasource = context.sources.add_or_update_postgres(
        name=DATASOURCE_NAME, connection_string=DB_URL
    )

    validators = []
    for table_name, build_suite in TABLE_SUITES.items():
        asset = datasource.add_table_asset(name=table_name, table_name=table_name, schema_name="cdm")
        batch_request: BatchRequest = asset.build_batch_request()
        suite_name = f"{table_name}_suite"
        context.add_or_update_expectation_suite(suite_name)
        validator = context.get_validator(batch_request=batch_request, expectation_suite_name=suite_name)
        build_suite(validator)
        validators.append((table_name, suite_name, batch_request))

    checkpoint = context.add_or_update_checkpoint(
        name="omop_cdm_checkpoint",
        validations=[
            {"batch_request": batch_request, "expectation_suite_name": suite_name}
            for _, suite_name, batch_request in validators
        ],
    )
    result = checkpoint.run()

    context.build_data_docs()

    print(f"\nData Quality run success: {result.success}")
    for run_result in result.run_results.values():
        stats = run_result["validation_result"]["statistics"]
        suite_name = run_result["validation_result"]["meta"]["expectation_suite_name"]
        print(
            f"  {suite_name}: {stats['successful_expectations']}/{stats['evaluated_expectations']} "
            f"expectations passed"
        )

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
