-- OMOP CDM: DEATH (one row per deceased person)
select
    person_id,
    death_date,
    32817 as death_type_concept_id  -- EHR
from {{ ref('stg_person') }}
where death_date is not null
