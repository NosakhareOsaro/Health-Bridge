#!/usr/bin/env python3
"""Generate a lightweight, Achilles-style data characterization report for the OMOP CDM.

OHDSI's real Achilles tool is an R package that computes ~200 standard
characterization queries and ships a full analytics web app. Pulling in R
for one report is out of scope for this project, so this script reproduces
the most useful subset (population summary, age/sex pyramid, condition
prevalence, visit mix, length of stay, mortality) directly in Python/pandas
against the same OMOP CDM tables, and renders a static HTML report.

Usage:
    python scripts/generate_achilles_report.py [--output report.html]
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import create_engine

DB_URL = os.environ.get(
    "OMOP_DB_SYNC_URL", "postgresql+psycopg2://omop:omop@localhost:5434/omop"
)
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
REFERENCE_YEAR = dt.date.today().year


def age_band(age: int) -> str:
    if age < 0:
        return "unknown"
    band_start = (age // 10) * 10
    return f"{band_start}-{band_start + 9}"


def build_report(engine) -> dict:
    person = pd.read_sql("select * from cdm.person", engine)
    visit = pd.read_sql("select * from cdm.visit_occurrence", engine)
    condition = pd.read_sql("select * from cdm.condition_occurrence", engine)
    measurement = pd.read_sql("select * from cdm.measurement", engine)
    observation = pd.read_sql("select * from cdm.observation", engine)
    death = pd.read_sql("select * from cdm.death", engine)
    concept = pd.read_sql("select concept_id, concept_name from cdm.concept", engine)

    summary_cards = [
        ("Persons", len(person)),
        ("Visits", len(visit)),
        ("Conditions", len(condition)),
        ("Measurements", len(measurement)),
        ("Observations", len(observation)),
        ("Deaths", len(death)),
    ]

    # --- age / sex pyramid ---
    person = person.copy()
    person["age"] = REFERENCE_YEAR - person["year_of_birth"]
    person["age_band"] = person["age"].apply(age_band)
    pyramid = (
        person.groupby(["age_band", "gender_concept_id"]).size().unstack(fill_value=0)
    )
    pyramid = pyramid.rename(columns={8507: "male", 8532: "female"})
    for col in ("male", "female"):
        if col not in pyramid.columns:
            pyramid[col] = 0
    max_count = max(1, pyramid[["male", "female"]].to_numpy().max())
    band_order = sorted(pyramid.index, key=lambda b: (b == "unknown", b))
    pyramid_rows = [
        {
            "age_band": band,
            "male_pct": round(100 * pyramid.loc[band, "male"] / max_count, 1),
            "female_pct": round(100 * pyramid.loc[band, "female"] / max_count, 1),
        }
        for band in band_order
    ]

    # --- top conditions ---
    cond_named = condition.merge(
        concept, left_on="condition_concept_id", right_on="concept_id", how="left"
    )
    cond_named["concept_name"] = cond_named["concept_name"].fillna("No matching concept")
    top_conditions = (
        cond_named.groupby("concept_name")
        .size()
        .sort_values(ascending=False)
        .head(10)
        .rename("occurrences")
        .reset_index()
    )

    # --- visit type distribution ---
    visit_named = visit.merge(
        concept, left_on="visit_concept_id", right_on="concept_id", how="left"
    )
    visit_named["concept_name"] = visit_named["concept_name"].fillna("No matching concept")
    visit_type_dist = (
        visit_named.groupby("concept_name").size().rename("visits").reset_index()
    )

    # --- length of stay ---
    visit_named["los_days"] = (
        pd.to_datetime(visit_named["visit_end_date"]) - pd.to_datetime(visit_named["visit_start_date"])
    ).dt.days
    los_summary = (
        visit_named.groupby("concept_name")["los_days"]
        .mean()
        .round(2)
        .rename("avg_los_days")
        .reset_index()
    )

    # --- mortality ---
    mortality = pd.DataFrame(
        [
            {
                "total_persons": len(person),
                "deaths": len(death),
                "mortality_rate_pct": round(100 * len(death) / max(1, len(person)), 2),
            }
        ]
    )

    return {
        "summary_cards": summary_cards,
        "pyramid_rows": pyramid_rows,
        "top_conditions_table": top_conditions.to_html(index=False, border=0),
        "visit_type_table": visit_type_dist.to_html(index=False, border=0),
        "los_table": los_summary.to_html(index=False, border=0),
        "mortality_table": mortality.to_html(index=False, border=0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "great_expectations" / "achilles_report.html",
    )
    args = parser.parse_args()

    engine = create_engine(DB_URL)
    context = build_report(engine)
    context["generated_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("achilles_report.html.jinja")
    html = template.render(**context)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
