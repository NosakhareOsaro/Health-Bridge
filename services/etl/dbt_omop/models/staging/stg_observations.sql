-- Resolves Observation -> person_id / visit_occurrence_id. The loader
-- already splits panel observations (e.g. blood pressure) into one row per
-- component, so every row here has at most one scalar value.
with patients as (
    select * from {{ ref('stg_patients') }}
),

visits as (
    select * from {{ ref('stg_encounters') }}
),

observations as (
    select * from {{ source('staging', 'observations') }}
)

select
    row_number() over (order by o.fhir_id) as observation_row_id,
    p.person_id,
    v.visit_occurrence_id,
    o.loinc_code,
    o.loinc_display,
    o.effective_date,
    o.value_quantity,
    o.value_unit,
    o.value_string
from observations o
inner join patients p on p.person_source_value = o.patient_fhir_id
left join visits v on v.visit_source_value = o.encounter_fhir_id
