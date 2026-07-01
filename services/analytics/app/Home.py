"""HealthBridge analytics -- Streamlit entry point.

Run with: streamlit run app/Home.py
"""

from __future__ import annotations

import streamlit as st
from db import get_engine
from measures import population_summary

st.set_page_config(page_title="HealthBridge Analytics", page_icon="\U0001FA7A", layout="wide")

st.title("HealthBridge Analytics")
st.caption(
    "Population health, A&E demand forecasting, and health-equity views over the OMOP CDM "
    "built by services/etl. All data is synthetic (Synthea)."
)

st.info(
    "Use the sidebar to navigate: **Population Health** (incidence, readmissions, LOS, "
    "age/sex pyramid), **A&E Forecasting** (Prophet demand model), and **Health Equity** "
    "(GIS choropleth)."
)

try:
    engine = get_engine()
    counts = population_summary(engine)
    cols = st.columns(len(counts))
    for col, (table, count) in zip(cols, counts.items()):
        col.metric(table.replace("_", " ").title(), f"{count:,}")
except Exception as exc:  # noqa: BLE001 -- surface a friendly message instead of a stack trace
    st.error(
        "Could not connect to the OMOP CDM database. Make sure `docker compose up omop-db` "
        f"is running and the ETL pipeline has been run at least once.\n\nDetails: {exc}"
    )
