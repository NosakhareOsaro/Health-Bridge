-- OMOP CDM v5.4 VISIT_OCCURRENCE. FHIR Encounter.class is mapped to the
-- standard OMOP Visit concepts (Inpatient/Outpatient/Emergency Room Visit).
select
    visit_occurrence_id,
    person_id,
    case class_code
        when 'IMP' then 9201  -- Inpatient Visit
        when 'AMB' then 9202  -- Outpatient Visit
        when 'EMER' then 9203 -- Emergency Room Visit
        else {{ var('no_matching_concept_id') }}
    end as visit_concept_id,
    period_start::date as visit_start_date,
    coalesce(period_end, period_start)::date as visit_end_date,
    32817 as visit_type_concept_id, -- EHR
    visit_source_value,
    class_code as visit_source_value_class
from {{ ref('stg_encounters') }}
