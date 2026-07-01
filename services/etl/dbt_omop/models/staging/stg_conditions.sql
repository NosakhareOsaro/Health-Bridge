-- Resolves Condition -> person_id / visit_occurrence_id and picks a single
-- "source value" for downstream concept mapping, preferring SNOMED (what
-- Synthea actually emits) and falling back to ICD-10 when present.
with patients as (
    select * from {{ ref('stg_patients') }}
),

visits as (
    select * from {{ ref('stg_encounters') }}
),

conditions as (
    select * from {{ source('staging', 'conditions') }}
)

select
    row_number() over (order by c.fhir_id) as condition_occurrence_id,
    p.person_id,
    v.visit_occurrence_id,
    c.icd10_code,
    c.snomed_code,
    coalesce(c.snomed_code, c.icd10_code) as condition_source_code,
    case when c.snomed_code is not null then 'SNOMED' else 'ICD10CM' end as condition_source_vocabulary,
    c.clinical_status,
    c.onset_date,
    c.recorded_date
from conditions c
inner join patients p on p.person_source_value = c.patient_fhir_id
left join visits v on v.visit_source_value = c.encounter_fhir_id
