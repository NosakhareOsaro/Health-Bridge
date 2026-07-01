-- OMOP CDM v5.4 MEASUREMENT: numeric-valued Observations (vitals/labs) whose
-- LOINC code maps to a concept in the Measurement domain.
with observations as (
    select * from {{ ref('stg_observations') }}
),

loinc_concept as (
    select concept_id, concept_code
    from {{ ref('concept') }}
    where vocabulary_id = 'LOINC' and domain_id = 'Measurement'
)

select
    o.observation_row_id as measurement_id,
    o.person_id,
    o.visit_occurrence_id,
    coalesce(lc.concept_id, {{ var('no_matching_concept_id') }}) as measurement_concept_id,
    o.effective_date::date as measurement_date,
    32817 as measurement_type_concept_id, -- EHR
    o.value_quantity as value_as_number,
    o.loinc_code as measurement_source_value,
    o.value_unit as unit_source_value
from observations o
inner join loinc_concept lc on lc.concept_code = o.loinc_code
where o.value_quantity is not null
