-- OMOP CDM: MEASUREMENT (numeric Synthea observations, LOINC source codes)
with o as (
    select * from {{ source('bronze', 'observations') }} where lower(type) = 'numeric'
),
p as (select person_id, person_source_value from {{ ref('stg_person') }}),
v as (select visit_occurrence_id, visit_source_id from {{ ref('stg_visit') }})

select
    row_number() over ()                          as measurement_id,
    p.person_id,
    0                                             as measurement_concept_id,
    cast(substr(o.date, 1, 10) as date)           as measurement_date,
    32817                                         as measurement_type_concept_id,
    try_cast(o.value as double)                   as value_as_number,
    o.units                                       as unit_source_value,
    o.code                                        as measurement_source_value,
    v.visit_occurrence_id
from o
inner join p on o.patient  = p.person_source_value
left  join v on o.encounter = v.visit_source_id
