# ADR-0004: Split schema ownership -- Alembic for staging, dbt for OMOP CDM

## Status

Accepted

## Context

The project brief asks for both a dbt-based FHIR-to-OMOP transformation layer *and*
Alembic migrations for schema versioning. Used naively, these two tools would compete to
own the same tables: dbt's `table` materialization already issues `CREATE TABLE`/`DROP
TABLE` DDL for every model it manages, so if Alembic also tried to version the OMOP CDM
tables, the two systems would fight over who is allowed to change them.

## Decision

Split ownership cleanly by schema:

- **`staging` schema**: a flattened, typed landing zone close to the FHIR shape
  (`staging.patients`, `.encounters`, `.conditions`, `.observations`, plus an
  `etl_batches` audit table). Owned and versioned by **Alembic**, using SQLAlchemy 2.0
  async models as the source of truth. The Python loader (`load_fhir_to_staging.py`)
  writes here directly.
- **`cdm` schema**: the OMOP CDM v5.4 tables plus the seeded vocabulary subset. Owned and
  materialized entirely by **dbt** (`table` models reading `staging.*` as `source()`s).

## Rationale

- **No DDL ownership conflict.** Alembic never touches `cdm.*`; dbt never touches
  `staging.*`. Each tool's migration/versioning story stays coherent on its own side.
- **Alembic fits the staging layer's actual shape.** Staging tables are simple,
  OLTP-style tables an application writer inserts/updates rows into directly -- exactly
  the case SQLAlchemy + Alembic is designed for, and versioning them (adding a
  `death_date` column, adding an index) is a normal Alembic migration.
- **dbt fits the OMOP layer's actual shape.** The CDM tables are pure SQL
  transformations of the staging tables (surrogate key assignment, concept mapping,
  domain routing) with no independent write path -- exactly dbt's model. dbt's built-in
  testing (`not_null`/`unique`/`relationships`/`accepted_values`) doubles as schema
  validation for this layer, so a second migration tool would be redundant here.
- **Both tools stay genuinely useful** rather than one being included only to tick a box:
  Alembic's `upgrade`/`downgrade` are exercised for real (see `services/etl/README.md`),
  and dbt's `seeds`/`models`/`tests` are exercised for real (74 passing steps in the
  reference run).

## Consequences

- A contributor changing the shape of clinical data flowing through the pipeline may need
  to touch two different migration mechanisms depending on which schema is affected --
  worth documenting clearly (done in `services/etl/README.md`) so it isn't surprising.
- If a future requirement needs the `cdm` schema to support genuinely incremental,
  versioned schema changes independent of a full `dbt run` (e.g. a hotfix to one column's
  type without recomputing every model), that would need to be revisited -- dbt's `table`
  materialization recreates the table on every run, which is fine for a batch ETL but not
  for a system needing zero-downtime schema evolution.
