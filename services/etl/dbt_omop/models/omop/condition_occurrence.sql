-- OMOP CDM v5.4 CONDITION_OCCURRENCE.
--
-- This is the model that actually performs ICD-10/SNOMED -> OMOP concept
-- mapping: it looks up the source code in the seeded `concept` vocabulary,
-- then (for non-standard source vocabularies like ICD10CM) follows the
-- `concept_relationship` "Maps to" edge to the standard concept, exactly as
-- a full OHDSI Athena vocabulary load would work -- just against a small,
-- representative subset instead of the full ~10M row vocabulary. See
-- services/etl/dbt_omop/seeds/ for the subset and how to swap in the real
-- Athena export.
with conditions as (
    select * from {{ ref('stg_conditions') }}
),

source_concept as (
    select concept_id, concept_code, vocabulary_id, standard_concept
    from {{ ref('concept') }}
    where vocabulary_id in ('SNOMED', 'ICD10CM')
),

mapped as (
    select
        c.*,
        sc.concept_id as source_concept_id,
        sc.standard_concept,
        maps_to.concept_id_2 as mapped_standard_concept_id
    from conditions c
    left join source_concept sc
        on sc.concept_code = c.condition_source_code
        and sc.vocabulary_id = c.condition_source_vocabulary
    left join {{ ref('concept_relationship') }} maps_to
        on maps_to.concept_id_1 = sc.concept_id
        and maps_to.relationship_id = 'Maps to'
)

select
    condition_occurrence_id,
    person_id,
    visit_occurrence_id,
    coalesce(
        case when standard_concept = 'S' then source_concept_id end,
        mapped_standard_concept_id,
        {{ var('no_matching_concept_id') }}
    ) as condition_concept_id,
    coalesce(source_concept_id, {{ var('no_matching_concept_id') }}) as condition_source_concept_id,
    condition_source_code as condition_source_value,
    coalesce(onset_date, recorded_date) as condition_start_date,
    32817 as condition_type_concept_id -- EHR
from mapped
