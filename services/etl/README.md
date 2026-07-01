# etl

Synthea &rarr; FHIR R4 &rarr; OMOP CDM v5.4 ETL pipeline: synthetic patient generation, a
staging layer versioned with Alembic, and a dbt project that transforms staging data into
the OMOP Common Data Model with ICD-10/SNOMED/LOINC concept mapping, backed by Great
Expectations data-quality checks and a lightweight Achilles-style characterization report.

## Pipeline

```
Synthea (Java)  --FHIR R4 bundles-->  scripts/load_fhir_to_staging.py  --async SQLAlchemy-->  staging.*
                                                                                                  |
                                                                                          dbt (seeds + models)
                                                                                                  v
                                                                                                cdm.*  (OMOP CDM v5.4)
                                                                                                  |
                                                                            Great Expectations + Achilles-style report
```

- **`staging` schema** -- a flattened, typed landing zone close to the FHIR shape. Schema
  versioning is handled by **Alembic** (`alembic/`), not dbt.
- **`cdm` schema** -- the OMOP CDM v5.4 tables, materialized and transformed entirely by
  **dbt** (`dbt_omop/`). See `docs/adr/0004-alembic-for-staging-dbt-for-omop.md` for why
  responsibility is split this way.

## Running the full pipeline locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 1. Generate synthetic patients (requires a Java 17+ runtime on PATH)
./scripts/generate_synthea.sh 25 Massachusetts

# 2. Stand up the OMOP Postgres warehouse and apply the staging schema
docker compose -f ../../docker-compose.yml up -d omop-db
export OMOP_DB_ASYNC_URL="postgresql+asyncpg://omop:omop@localhost:5434/omop"
alembic upgrade head

# 3. Load FHIR bundles into the staging schema
python3 scripts/load_fhir_to_staging.py --input-dir synthea/output/fhir

# 4. Transform staging -> OMOP CDM with dbt
cd dbt_omop
export DBT_PROFILES_DIR=.
export OMOP_DB_HOST=localhost OMOP_DB_PORT=5434 OMOP_DB_USER=omop OMOP_DB_PASSWORD=omop OMOP_DB_NAME=omop
dbt build   # seeds + models + schema tests
cd ..

# 5. Data quality checks + characterization report
export OMOP_DB_SYNC_URL="postgresql+psycopg2://omop:omop@localhost:5434/omop"
python3 scripts/run_data_quality_checks.py
python3 scripts/generate_achilles_report.py   # writes great_expectations/achilles_report.html
```

Every step above has been run end-to-end against a real Postgres instance with a real
Synthea-generated population as part of building this project (not just unit-tested in
isolation).

## ICD-10 / SNOMED / LOINC / RxNorm concept mapping

`dbt_omop/seeds/concept.csv` and `concept_relationship.csv` are a **small, hand-picked
subset** of the OHDSI vocabulary, not the full OMOP Standardized Vocabularies:

- Gender/Race/Ethnicity concepts (`8507`, `8532`, `8551`, `8527`, `8516`, ...) are the real,
  stable OMOP standard concepts for those tiny vocabularies.
- Visit and Type Concept ids (`9201`/`9202`/`9203`, `32817`) are likewise real, ubiquitous
  OMOP standard concepts.
- The ~20 SNOMED/ICD-10-CM/LOINC condition and measurement concepts use the OMOP-reserved
  **local concept_id range (`>= 2,000,000,000`)** and are *not* official Athena concept ids
  -- they exist only so `condition_occurrence.sql` has something real to join against and
  demonstrate the mapping mechanism (`concept` lookup -> `concept_relationship` "Maps to"
  -> standard concept).

**To use the real vocabulary:** download the OMOP Standardized Vocabularies from
[OHDSI Athena](https://athena.ohdsi.org/) (free registration required), and replace the
`concept`/`concept_relationship`/`vocabulary`/`domain` seed CSVs with the full Athena
export (or load them directly into the `cdm` schema via `psql \copy` and drop them as dbt
seeds, since the full vocabulary is ~10M rows and too large for dbt's seed mechanism).
`condition_occurrence.sql`, `person.sql`, `visit_occurrence.sql`, and `measurement.sql`
require no changes -- they join by `vocabulary_id` + `concept_code`, which works the same
whether the `concept` table has 40 rows or 10 million.

## Great Expectations

`scripts/run_data_quality_checks.py` builds a file-backed GE project under
`great_expectations/gx/` with expectation suites for `person`, `visit_occurrence`,
`condition_occurrence`, and `measurement`, runs them as a checkpoint, and exits non-zero on
failure (suitable for CI). Suite/checkpoint definitions are committed;
`great_expectations/gx/uncommitted/` (Data Docs, validation run history) is regenerated
per-run and gitignored.

## Achilles-style report

`scripts/generate_achilles_report.py` is a lightweight, from-scratch substitute for OHDSI's
[Achilles](https://github.com/OHDSI/Achilles) R package (population summary, age/sex
pyramid, condition prevalence, visit mix, length of stay, mortality) rendered as a static
HTML file at `great_expectations/achilles_report.html`. Real Achilles computes ~200
characterization queries and ships a full R Shiny app; this covers the subset most useful
for a portfolio-scale dataset without adding an R dependency to the project.

## Tests

```bash
pytest -v
```

Covers the FHIR-parsing/flattening helpers in `scripts/load_fhir_to_staging.py`
(reference stripping, US Core race/ethnicity extension parsing, panel-observation
splitting, etc.) with inline fixtures -- no database required. The staging-load,
dbt build, and Great Expectations steps are database-dependent and are verified manually
against a live docker-compose stack (see "Running the full pipeline locally" above).

## Known simplifications (portfolio scope)

- Synthea's synthetic conditions are almost entirely SNOMED-coded (not ICD-10); the ICD-10
  side of the mapping is exercised by the vocabulary subset/tests rather than by Synthea
  output itself. A claims-based source system would supply ICD-10 more often.
- `condition_type_concept_id`/`visit_type_concept_id`/etc. are all hardcoded to `32817`
  ("EHR") for simplicity -- a production ETL would distinguish e.g. primary vs. secondary
  diagnosis.
- `observation_period` is inferred from encounter history, not payer enrollment data.
