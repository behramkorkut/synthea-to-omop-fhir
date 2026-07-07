-- OMOP CDM: OBSERVATION (non-numeric Synthea observations)
with o as (
    select * from {{ source('bronze', 'observations') }} where lower(type) <> 'numeric'
),
p as (select person_id, person_source_value from {{ ref('stg_person') }}),
v as (select visit_occurrence_id, visit_source_id from {{ ref('stg_visit') }})

select
    row_number() over ()                          as observation_id,
    p.person_id,
    0                                             as observation_concept_id,
    cast(substr(o.date, 1, 10) as date)           as observation_date,
    32817                                         as observation_type_concept_id,
    o.value                                       as value_as_string,
    o.units                                       as unit_source_value,
    o.code                                        as observation_source_value,
    v.visit_occurrence_id
from o
inner join p on o.patient  = p.person_source_value
left  join v on o.encounter = v.visit_source_id
