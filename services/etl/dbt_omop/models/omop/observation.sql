-- OMOP CDM v5.4 OBSERVATION: everything from stg_observations that isn't a
-- numeric Measurement (e.g. free-text/coded findings, or any LOINC code not
-- in the seeded Measurement subset) lands here instead, per the OMOP
-- convention that Observation is the catch-all clinical-fact table.
with observations as (
    select * from {{ ref('stg_observations') }}
),

loinc_concept as (
    select concept_id, concept_code
    from {{ ref('concept') }}
    where vocabulary_id = 'LOINC'
)

select
    o.observation_row_id as observation_id,
    o.person_id,
    o.visit_occurrence_id,
    coalesce(lc.concept_id, {{ var('no_matching_concept_id') }}) as observation_concept_id,
    o.effective_date::date as observation_date,
    32817 as observation_type_concept_id, -- EHR
    o.value_string as value_as_string,
    o.loinc_code as observation_source_value
from observations o
left join loinc_concept lc
    on lc.concept_code = o.loinc_code and lc.concept_code not in (
        select concept_code from {{ ref('concept') }} where vocabulary_id = 'LOINC' and domain_id = 'Measurement'
    )
where o.value_quantity is null
