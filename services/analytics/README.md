# analytics

Population health dashboard, ICD-10 -> SNOMED CT mapping utility, and (from Phase 4) A&E
demand forecasting + health-equity views, all built on top of the OMOP CDM v5.4 tables
produced by `services/etl`.

## Dashboard tooling: Streamlit instead of Power BI

The project brief calls for a Power BI-style star-schema dashboard, with an explicit
fallback to Streamlit if Power BI tooling isn't available in this environment. This build
environment is a headless macOS/Linux CI-style container with no Windows desktop, so
**Power BI Desktop cannot run here at all** -- there is no `.pbix` to produce, and a
screenshot of one would not be a real, working artifact. Streamlit was used instead because
it is the one dashboard tool in the brief's fallback list that can actually be built,
run, and verified end-to-end in this environment, backed by the same OMOP CDM Postgres
tables a Power BI report would query. See `docs/adr/0003-dashboard-tooling-choice.md` for
the full reasoning.

The underlying **star-schema thinking still applies**: `cdm.person` is the dimension table
patients are grouped by (age band, gender, race, ethnicity), and
`cdm.condition_occurrence` / `cdm.visit_occurrence` / `cdm.measurement` are the fact tables
the dashboard's measures aggregate -- the exact shape a Power BI model would use if pointed
at the same warehouse.

## Running it

```bash
docker compose up -d omop-db
# ... run the services/etl pipeline at least once (see its README) ...

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export OMOP_DB_URL="postgresql://omop:omop@localhost:5434/omop"
streamlit run app/Home.py
```

Or via Docker Compose: `docker compose up analytics-dashboard` (served at
`http://localhost:8501`).

## Population Health page

`app/pages/1_Population_Health.py`, backed by `app/measures.py`, computes directly from the
OMOP CDM tables:

- **Age/sex population pyramid** -- from `cdm.person`.
- **Disease incidence** -- condition occurrences per 1,000 person-years of observation
  (person-time from `cdm.observation_period`), joined to `cdm.concept` for readable names.
- **Readmission rate** -- % of inpatient visits (`visit_concept_id = 9201`) followed by
  another inpatient visit for the same person within a configurable window (default 30
  days). A simplified version of the standard measure -- it does not exclude planned
  readmissions/transfers.
- **Length-of-stay trends** -- average LOS by visit type and by month.

All four are plain functions taking a SQLAlchemy `Engine` and returning a `DataFrame`, so
they're covered by integration tests (`tests/test_measures.py`) against the same live OMOP
database, not mocks.

## ICD-10 -> SNOMED CT mapping utility

`mapping/icd10_to_snomed.py` is a standalone CLI/library that looks up an ICD-10-CM code in
the OMOP vocabulary tables and follows the "Maps to" relationship to the standard SNOMED CT
concept -- the same mechanism `services/etl`'s dbt models use internally, exposed here as a
reusable tool for analysts who just need a code translated:

```bash
export OMOP_DB_URL="postgresql://omop:omop@localhost:5434/omop"
python3 mapping/icd10_to_snomed.py J01.90
#   J01.90 (Acute sinusitis, unspecified)  ->  444814009 (Viral sinusitis (disorder))

python3 mapping/icd10_to_snomed.py --batch codes.csv --output mapped.csv
python3 mapping/icd10_to_snomed.py --all   # dump the full seeded crosswalk
```

Only the small seeded vocabulary subset from `services/etl/dbt_omop/seeds/` is loaded by
default -- see that service's README for how to load the full OHDSI Athena vocabulary.

## A&E demand forecasting (Prophet)

`app/pages/2_AE_Forecasting.py`, backed by `forecasting/`:

- `generate_ae_attendance_data.py` fabricates a **synthetic** daily A&E attendance series
  (weekly + winter-surge seasonality, a slow upward trend, noise, and a few outbreak-style
  spike days) -- there is no real attendance data anywhere in this project.
- `train_prophet_model.py` fits a `Prophet` model, evaluates accuracy on a holdout window
  (typically ~4% MAPE on this synthetic series), and forecasts forward.
- The dashboard page runs this live (cached with `st.cache_resource`/`st.cache_data` so the
  page stays responsive), plotting actual history vs. forecast with a shaded confidence
  interval and a "today" marker -- the "real-time forecasted vs. actual" view called for in
  the brief.

## Health equity view (GIS choropleth)

`app/pages/3_Health_Equity.py`, backed by `equity/generate_equity_data.py`:

- Fabricates a 5x5 grid of **synthetic** square "service area" polygons around Boston, MA
  (consistent with where this project's Synthea population is generated) using `shapely`,
  assigns each a synthetic deprivation index, chronic-disease prevalence, life expectancy,
  and population via `geopandas`.
- Renders a choropleth with `folium.Choropleth` (selectable metric) plus hover tooltips.
- There are no real ZIP/ZCTA boundary files or demographic data behind this -- downloading
  the real US Census TIGER/Line shapefiles was judged out of scope for a portfolio ETL, and
  is called out explicitly in the page itself, not just in this README.

## Tests

```bash
pytest -v
```

`test_measures.py` and `test_icd10_to_snomed.py` are integration tests against a live OMOP
CDM Postgres (they `pytest.skip` if it isn't reachable, rather than mocking the database).
`test_forecasting.py` and `test_equity.py` run the real Prophet/geopandas pipelines against
generated synthetic data and need no database.

## Known simplifications (portfolio scope)

- Readmission/incidence rates are computed over whatever population size the ETL loaded
  (63 patients in the reference run behind the committed Achilles report and dashboard
  screenshots) -- rates will be noisy/sparse at that scale. Generate a larger Synthea
  population (`./scripts/generate_synthea.sh 500`) for more realistic numbers.
- The readmission measure doesn't exclude planned admissions or transfers, unlike the full
  CMS/NHS readmission methodologies.
- The A&E attendance series and health-equity regions/metrics are both entirely synthetic
  and clearly labeled as such in the UI -- swap in a real time series or real GIS boundary
  files (e.g. ONS/Census shapefiles) to make either page reflect a real population.
