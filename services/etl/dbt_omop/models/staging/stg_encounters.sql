-- Assigns a surrogate visit_occurrence_id and resolves the FHIR patient
-- reference down to the integer person_id minted in stg_patients.
with patients as (
    select * from {{ ref('stg_patients') }}
),

encounters as (
    select * from {{ source('staging', 'encounters') }}
)

select
    row_number() over (order by e.fhir_id) as visit_occurrence_id,
    e.fhir_id as visit_source_value,
    p.person_id,
    e.status,
    e.class_code,
    e.type_code,
    e.type_display,
    e.period_start,
    e.period_end
from encounters e
inner join patients p on p.person_source_value = e.patient_fhir_id
