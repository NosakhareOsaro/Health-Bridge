"""Population health dashboard: disease incidence, readmissions, LOS trends, age/sex pyramid.

This is the Streamlit dashboard called for in the project brief -- built here
instead of a Power BI .pbix file, since Power BI Desktop isn't available in
this (Linux/CI-friendly, non-Windows) build environment. See the analytics
service README for the full rationale.
"""

from __future__ import annotations

import altair as alt
import streamlit as st
from db import get_engine
from measures import age_sex_pyramid, disease_incidence, length_of_stay_trends, readmission_rate

st.set_page_config(page_title="Population Health | HealthBridge", layout="wide")
st.title("Population Health Dashboard")
st.caption("All measures computed live from the OMOP CDM v5.4 tables. Synthetic data only.")

engine = get_engine()

st.header("Age / sex pyramid")
pyramid = age_sex_pyramid(engine)
if pyramid.empty:
    st.warning("No person data found -- has the ETL pipeline been run?")
else:
    pyramid = pyramid.copy()
    pyramid["signed_count"] = pyramid.apply(
        lambda r: -r["count"] if r["gender"] == "Male" else r["count"], axis=1
    )
    band_order = sorted(pyramid["age_band"].unique(), key=lambda b: int(b.split("-")[0]))
    chart = (
        alt.Chart(pyramid)
        .mark_bar()
        .encode(
            x=alt.X("signed_count:Q", title="Population count", axis=alt.Axis(labelExpr="abs(datum.value)")),
            y=alt.Y("age_band:N", sort=band_order, title="Age band"),
            color=alt.Color(
                "gender:N",
                scale=alt.Scale(domain=["Male", "Female", "Unknown"], range=["#4c78a8", "#e45756", "#999"]),
            ),
            tooltip=["age_band", "gender", "count"],
        )
        .properties(height=400)
    )
    st.altair_chart(chart, use_container_width=True)

st.header("Disease incidence")
st.caption("Occurrences per 1,000 person-years of observation.")
incidence = disease_incidence(engine)
if incidence.empty:
    st.warning("No condition data found.")
else:
    top_n = incidence.head(15)
    bar = (
        alt.Chart(top_n)
        .mark_bar()
        .encode(
            x=alt.X("occurrences:Q", title="Occurrences"),
            y=alt.Y("concept_name:N", sort="-x", title=None),
            tooltip=["concept_name", "occurrences", "patients_affected", "incidence_per_1000_person_years"],
        )
        .properties(height=450)
    )
    st.altair_chart(bar, use_container_width=True)
    with st.expander("Full incidence table"):
        st.dataframe(incidence, use_container_width=True)

col_a, col_b = st.columns(2)

with col_a:
    st.header("Readmission rate")
    window = st.slider("Readmission window (days)", min_value=7, max_value=90, value=30, step=1)
    readmit = readmission_rate(engine, window_days=window)
    if not readmit.empty:
        row = readmit.iloc[0]
        st.metric(
            f"{window}-day inpatient readmission rate",
            f"{row['readmission_rate_pct']}%",
            help=f"{row['readmissions']} of {row['total_inpatient_visits']} inpatient visits",
        )

with col_b:
    st.header("Length of stay trends")
    los = length_of_stay_trends(engine)
    if los.empty:
        st.warning("No visit data found.")
    else:
        line = (
            alt.Chart(los)
            .mark_line(point=True)
            .encode(
                x=alt.X("month:T", title="Month"),
                y=alt.Y("avg_los_days:Q", title="Avg LOS (days)"),
                color="visit_type:N",
                tooltip=["month", "visit_type", "avg_los_days", "visit_count"],
            )
            .properties(height=350)
        )
        st.altair_chart(line, use_container_width=True)
