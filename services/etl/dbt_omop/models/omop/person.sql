-- OMOP CDM v5.4 PERSON table.
-- Gender is mapped with an explicit CASE (the Gender vocabulary only has 3
-- concepts, so a join adds no clarity); race/ethnicity are mapped by joining
-- the seeded `concept` vocabulary subset, demonstrating the general
-- source-value -> standard-concept pattern used throughout this project.
with patients as (
    select * from {{ ref('stg_patients') }}
),

race_concept as (
    select concept_id, concept_name from {{ ref('concept') }} where vocabulary_id = 'Race'
),

ethnicity_concept as (
    select concept_id, concept_name from {{ ref('concept') }} where vocabulary_id = 'Ethnicity'
)

select
    p.person_id,
    case p.gender
        when 'male' then 8507
        when 'female' then 8532
        else 8551
    end as gender_concept_id,
    p.year_of_birth,
    p.month_of_birth,
    p.day_of_birth,
    p.birth_date as birth_datetime,
    coalesce(rc.concept_id, {{ var('no_matching_concept_id') }}) as race_concept_id,
    coalesce(ec.concept_id, {{ var('no_matching_concept_id') }}) as ethnicity_concept_id,
    p.person_source_value,
    p.gender as gender_source_value,
    p.race as race_source_value,
    p.ethnicity as ethnicity_source_value,
    p.address_state as location_source_value,
    p.death_date is not null as is_deceased
from patients p
left join race_concept rc on rc.concept_name = p.race
left join ethnicity_concept ec on ec.concept_name = p.ethnicity
