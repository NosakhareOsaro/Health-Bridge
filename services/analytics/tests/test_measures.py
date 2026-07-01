"""Integration tests for population health measures against a live OMOP CDM.

These run against the real Postgres database populated by services/etl (see
conftest.py) rather than mocks, since the whole point of these functions is
correct SQL against the real OMOP schema.
"""

from __future__ import annotations

from measures import (
    age_sex_pyramid,
    disease_incidence,
    length_of_stay_trends,
    population_summary,
    readmission_rate,
)


def test_population_summary_returns_positive_counts(live_engine):
    summary = population_summary(live_engine)
    assert summary["person"] > 0
    assert summary["visit_occurrence"] > 0
    assert set(summary) == {"person", "visit_occurrence", "condition_occurrence", "measurement", "death"}


def test_age_sex_pyramid_covers_all_persons(live_engine):
    pyramid = age_sex_pyramid(live_engine)
    summary = population_summary(live_engine)
    assert pyramid["count"].sum() == summary["person"]
    assert set(pyramid["gender"]).issubset({"Male", "Female", "Unknown"})


def test_disease_incidence_has_expected_columns_and_nonnegative_rates(live_engine):
    incidence = disease_incidence(live_engine)
    assert not incidence.empty
    assert list(incidence.columns) == [
        "concept_name",
        "occurrences",
        "patients_affected",
        "incidence_per_1000_person_years",
    ]
    assert (incidence["occurrences"] > 0).all()
    assert (incidence["incidence_per_1000_person_years"] >= 0).all()


def test_readmission_rate_is_a_valid_percentage(live_engine):
    result = readmission_rate(live_engine, window_days=30)
    assert len(result) == 1
    row = result.iloc[0]
    assert 0 <= row["readmission_rate_pct"] <= 100
    assert row["readmissions"] <= row["total_inpatient_visits"]


def test_length_of_stay_trends_nonnegative(live_engine):
    los = length_of_stay_trends(live_engine)
    assert not los.empty
    assert (los["avg_los_days"] >= 0).all()
    assert (los["visit_count"] > 0).all()
