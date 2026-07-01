-- Assigns a stable integer surrogate key (person_id) to each FHIR Patient,
-- since OMOP requires integer primary keys but FHIR ids are strings/UUIDs.
select
    row_number() over (order by fhir_id) as person_id,
    fhir_id as person_source_value,
    gender,
    birth_date,
    extract(year from birth_date)::int as year_of_birth,
    extract(month from birth_date)::int as month_of_birth,
    extract(day from birth_date)::int as day_of_birth,
    death_date,
    race,
    ethnicity,
    address_city,
    address_state,
    address_postal_code
from {{ source('staging', 'patients') }}
