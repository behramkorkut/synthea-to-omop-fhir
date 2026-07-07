-- OMOP CDM: DRUG_EXPOSURE (from Synthea medications, RxNorm source codes)
with m as (
    select * from {{ source('bronze', 'medications') }}
),
p as (select person_id, person_source_value from {{ ref('stg_person') }}),
v as (select visit_occurrence_id, visit_source_id from {{ ref('stg_visit') }})

select
    row_number() over ()                          as drug_exposure_id,
    p.person_id,
    0                                             as drug_concept_id,
    cast(substr(m.start, 1, 10) as date)          as drug_exposure_start_date,
    coalesce(cast(nullif(substr(m.stop, 1, 10), '') as date),
             cast(substr(m.start, 1, 10) as date)) as drug_exposure_end_date,
    32817                                         as drug_type_concept_id,
    m.code                                        as drug_source_value,
    v.visit_occurrence_id
from m
inner join p on m.patient  = p.person_source_value
left  join v on m.encounter = v.visit_source_id
