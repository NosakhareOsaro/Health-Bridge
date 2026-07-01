# ADR-0003: Use Streamlit instead of Power BI for the analytics dashboards

## Status

Accepted

## Context

The project brief calls for a Power BI-style star-schema population health dashboard,
explicitly allowing a fallback ("R Shiny / Streamlit") if Power BI tooling isn't available
in the build environment, with the substitution documented clearly.

This build environment is a headless macOS/Linux, CI-style container with no Windows
desktop and no Power BI Desktop installation. Power BI Desktop is a Windows-only
application; there is no way to author or render a real `.pbix` file here, and a
screenshot of one would not be a real, runnable artifact -- it would just be a claim.

Options considered:

1. Produce a `.pbix`-shaped *specification document* (measures, relationships, visuals)
   without an actual working file, plus mocked-up screenshots.
2. Build the dashboard in Streamlit end-to-end, actually running against the real OMOP CDM
   Postgres tables.
3. Build the dashboard in R Shiny instead (also allowed by the brief).

## Decision

Build the population health, A&E forecasting, and health-equity dashboards in Streamlit.

## Rationale

- **A working artifact beats a plausible-looking one.** Option 1 would produce something
  that *looks* like a deliverable but cannot actually be run, tested, or verified --
  directly against this project's stated quality bar ("all code must actually run").
- **Streamlit vs. R Shiny:** the rest of this project's analytics/ETL stack is Python
  (pandas, SQLAlchemy, dbt, Prophet, geopandas). Streamlit shares that stack directly --
  `measures.py`'s functions are plain Python callables reused by both the dashboard and the
  pytest suite. R Shiny would require standing up a second language runtime for one
  component with no reuse benefit.
- **Same underlying data model.** The dashboard's measures are computed directly from
  `cdm.person` / `cdm.condition_occurrence` / `cdm.visit_occurrence` / `cdm.measurement` --
  exactly the fact/dimension tables a Power BI model would be built against if pointed at
  the same warehouse. Swapping in real Power BI Desktop later is a matter of connecting it
  to the same Postgres tables, not redesigning the data model.

## Consequences

- No `.pbix` file exists in this repository. A reviewer who specifically wants to see a
  Power BI report will need to connect Power BI Desktop to the `omop-db` Postgres
  container themselves (see `services/analytics/README.md` for connection details) --
  documented as a natural next step, not hidden.
- DAX-equivalent measures are expressed as SQL + pandas in `measures.py` rather than as
  Power BI DAX expressions. The measure *logic* (incidence per 1,000 person-years,
  readmission window, LOS averages) is the same regardless of which tool renders it.
- Streamlit dashboards are simpler to keep in version control and CI (plain Python, no
  binary report file to diff) but lack Power BI's built-in cross-filtering /
  drill-through UX out of the box.
