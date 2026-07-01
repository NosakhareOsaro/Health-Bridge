"""Population health measures computed directly from the OMOP CDM v5.4 tables.

Every function takes a SQLAlchemy ``Engine`` and returns a pandas
``DataFrame``, so they can be unit-tested against any Postgres instance
(including the real one produced by ``services/etl``) and reused by both the
Streamlit UI and the test suite.
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

GENDER_LABELS = {8507: "Male", 8532: "Female", 8551: "Unknown"}


def age_sex_pyramid(engine: Engine, reference_year: int | None = None) -> pd.DataFrame:
    """Counts of living-population age band x gender, for a population pyramid chart."""
    reference_year = reference_year or dt.date.today().year
    person = pd.read_sql("select person_id, gender_concept_id, year_of_birth from cdm.person", engine)
    person["age"] = reference_year - person["year_of_birth"]
    person["age_band"] = (person["age"] // 10 * 10).clip(lower=0).astype(str) + "-" + (
        (person["age"] // 10 * 10) + 9
    ).astype(str)
    person["gender"] = person["gender_concept_id"].map(GENDER_LABELS).fillna("Unknown")

    pyramid = (
        person.groupby(["age_band", "gender"]).size().rename("count").reset_index()
    )
    return pyramid


def disease_incidence(engine: Engine) -> pd.DataFrame:
    """Condition occurrence counts per 1,000 person-years of observation.

    Person-time is derived from ``observation_period``, which this project's
    dbt models infer from each person's encounter history (see
    services/etl/dbt_omop/models/omop/observation_period.sql).
    """
    query = text(
        """
        with person_years as (
            select sum(
                (observation_period_end_date - observation_period_start_date) / 365.25
            ) as total_person_years
            from cdm.observation_period
        ),
        condition_counts as (
            select
                co.condition_concept_id,
                coalesce(c.concept_name, 'No matching concept') as concept_name,
                count(*) as occurrences,
                count(distinct co.person_id) as patients_affected
            from cdm.condition_occurrence co
            left join cdm.concept c on c.concept_id = co.condition_concept_id
            group by co.condition_concept_id, c.concept_name
        )
        select
            cc.concept_name,
            cc.occurrences,
            cc.patients_affected,
            round((cc.occurrences / py.total_person_years) * 1000, 2) as incidence_per_1000_person_years
        from condition_counts cc
        cross join person_years py
        order by cc.occurrences desc
        """
    )
    return pd.read_sql(query, engine)


def readmission_rate(engine: Engine, window_days: int = 30) -> pd.DataFrame:
    """Unplanned-readmission-style measure: % of inpatient visits followed by
    another inpatient visit for the same person within ``window_days``.

    This is a simplified version of the standard 30-day readmission
    measure (it does not exclude planned readmissions or transfers).
    """
    query = text(
        """
        with inpatient as (
            select person_id, visit_occurrence_id, visit_start_date, visit_end_date
            from cdm.visit_occurrence
            where visit_concept_id = 9201
        ),
        readmissions as (
            select
                a.visit_occurrence_id,
                exists (
                    select 1 from inpatient b
                    where b.person_id = a.person_id
                    and b.visit_occurrence_id <> a.visit_occurrence_id
                    and b.visit_start_date > a.visit_end_date
                    and b.visit_start_date <= a.visit_end_date + make_interval(days => :window_days)
                ) as was_readmitted
            from inpatient a
        )
        select
            count(*) as total_inpatient_visits,
            sum(case when was_readmitted then 1 else 0 end) as readmissions,
            round(
                100.0 * sum(case when was_readmitted then 1 else 0 end) / greatest(count(*), 1), 2
            ) as readmission_rate_pct
        from readmissions
        """
    )
    return pd.read_sql(query, engine, params={"window_days": window_days})


def length_of_stay_trends(engine: Engine) -> pd.DataFrame:
    """Average length of stay (days) by visit type and by month."""
    query = text(
        """
        select
            coalesce(c.concept_name, 'No matching concept') as visit_type,
            date_trunc('month', v.visit_start_date)::date as month,
            round(avg(v.visit_end_date - v.visit_start_date), 2) as avg_los_days,
            count(*) as visit_count
        from cdm.visit_occurrence v
        left join cdm.concept c on c.concept_id = v.visit_concept_id
        group by visit_type, month
        order by month, visit_type
        """
    )
    return pd.read_sql(query, engine)


def population_summary(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        counts = {}
        for table in ("person", "visit_occurrence", "condition_occurrence", "measurement", "death"):
            counts[table] = conn.execute(text(f"select count(*) from cdm.{table}")).scalar_one()
    return counts
