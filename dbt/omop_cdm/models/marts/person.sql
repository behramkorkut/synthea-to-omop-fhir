-- OMOP CDM: PERSON
select
    person_id,
    gender_concept_id,
    extract(year  from birth_date)        as year_of_birth,
    extract(month from birth_date)        as month_of_birth,
    extract(day   from birth_date)        as day_of_birth,
    cast(birth_date as timestamp)         as birth_datetime,
    race_concept_id,
    ethnicity_concept_id,
    person_source_value,
    gender_source_value,
    race_source_value,
    ethnicity_source_value
from {{ ref('stg_person') }}
