# ADR-0001: Use OMOP CDM v5.4 instead of a custom analytics schema

## Status

Accepted

## Context

The ETL pipeline needs to land clinical data (extracted from FHIR) somewhere queryable for
population health analytics. Two broad options exist:

1. Design a bespoke, project-specific relational schema shaped around exactly the measures
   this project's dashboards need (disease incidence, readmissions, LOS, age/sex pyramids).
2. Adopt the OHDSI OMOP Common Data Model (CDM), a mature, standardized schema used across
   hundreds of real-world health data networks.

A custom schema would be faster to stand up initially -- fewer tables, no vocabulary
mapping step, no need to understand OMOP's conventions (concept ids, `visit_occurrence`
vs. `encounter`, standard vs. source concepts, the `0` "No matching concept" sentinel,
etc.).

## Decision

Use OMOP CDM v5.4 for the target warehouse schema (`cdm.*`), populated via dbt.

## Rationale

- **Portfolio signal.** OMOP CDM is the de facto standard for observational health data
  analytics (OHDSI, All of Us, several NHS regional data platforms). Demonstrating a real
  FHIR-to-OMOP ETL with concept mapping is a materially stronger signal of health
  informatics competency than a bespoke schema that only this project understands.
- **Interoperability.** Any tool built for OMOP (OHDSI Achilles, ATLAS, standard cohort
  definitions, PheKB phenotype libraries) would work against this warehouse with no
  changes, because the schema is standard.
- **Vocabulary mapping is the actual hard/interesting part.** A bespoke schema would let
  us skip ICD-10/SNOMED/LOINC -> concept mapping entirely, which is one of the explicit
  target skills for this project. Building it against OMOP's real `concept` /
  `concept_relationship` "Maps to" mechanism means the mapping logic transfers directly to
  a real deployment with the full Athena vocabulary loaded -- a bespoke mapping table would
  not.
- **Forces correct modeling discipline.** OMOP's separation of `condition_occurrence` /
  `measurement` / `observation` by domain, and standard vs. source concepts, mirrors real
  constraints (e.g. a lab value must have a numeric `value_as_number`) that a custom schema
  could accidentally paper over.

## Consequences

- More upfront schema complexity than a bespoke design: seven CDM tables plus four
  vocabulary tables versus a handful of ad hoc ones.
- Only a small, hand-picked subset of the real OMOP Standardized Vocabularies is loaded
  (see `services/etl/README.md`) -- most condition/measurement codes outside that subset
  will map to concept_id `0` ("No matching concept") until a full OHDSI Athena vocabulary
  download replaces the seed CSVs. This is documented, not hidden.
- Contributors need at least a basic understanding of OMOP conventions to extend the
  models, which has a real (if modest) learning curve compared to a from-scratch schema.
