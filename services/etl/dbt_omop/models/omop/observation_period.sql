-- OMOP CDM v5.4 OBSERVATION_PERIOD: one row per person spanning their
-- earliest to latest recorded encounter, inferred from the encounter history
-- (a standard simplification when no payer/enrollment data is available).
select
    row_number() over (order by person_id) as observation_period_id,
    person_id,
    min(period_start)::date as observation_period_start_date,
    max(coalesce(period_end, period_start))::date as observation_period_end_date,
    {{ var('no_matching_concept_id') }} as period_type_concept_id
from {{ ref('stg_encounters') }}
group by person_id
