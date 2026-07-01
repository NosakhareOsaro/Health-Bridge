-- OMOP CDM v5.4 DEATH: one row per deceased person, from FHIR
-- Patient.deceasedDateTime.
select
    person_id,
    death_date,
    32817 as death_type_concept_id -- EHR
from {{ ref('stg_patients') }}
where death_date is not null
