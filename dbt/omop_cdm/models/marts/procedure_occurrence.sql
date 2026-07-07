-- OMOP CDM: PROCEDURE_OCCURRENCE (from Synthea procedures)
with pr as (
    select * from {{ source('bronze', 'procedures') }}
),
p as (select person_id, person_source_value from {{ ref('stg_person') }}),
v as (select visit_occurrence_id, visit_source_id from {{ ref('stg_visit') }})

select
    row_number() over ()                          as procedure_occurrence_id,
    p.person_id,
    0                                             as procedure_concept_id,
    cast(substr(pr.start, 1, 10) as date)         as procedure_date,
    32817                                         as procedure_type_concept_id,
    pr.code                                       as procedure_source_value,
    v.visit_occurrence_id
from pr
inner join p on pr.patient  = p.person_source_value
left  join v on pr.encounter = v.visit_source_id
