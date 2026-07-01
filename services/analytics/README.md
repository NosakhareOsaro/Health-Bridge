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

## Tests

```bash
pytest -v
```

These are integration tests against a live OMOP CDM Postgres (they `pytest.skip` if it
isn't reachable, rather than mocking the database), since the thing actually worth testing
here is the SQL against the real OMOP schema.

## Known simplifications (portfolio scope)

- Readmission/incidence rates are computed over whatever population size the ETL loaded
  (17 patients in the reference run) -- rates will be noisy/sparse at that scale. Generate
  a larger Synthea population (`./scripts/generate_synthea.sh 500`) for more realistic
  numbers.
- The readmission measure doesn't exclude planned admissions or transfers, unlike the full
  CMS/NHS readmission methodologies.
