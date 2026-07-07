-- OMOP CDM: CONDITION_OCCURRENCE (from Synthea conditions, SNOMED-CT source codes)
-- condition_concept_id is left at 0 (unmapped); standard mapping is done via the
-- OHDSI vocabulary (Athena) in production — see docs/omop_mapping.md.
with c as (
    select * from {{ source('bronze', 'conditions') }}
),
p as (select person_id, person_source_value from {{ ref('stg_person') }}),
v as (select visit_occurrence_id, visit_source_id from {{ ref('stg_visit') }})

select
    row_number() over ()                          as condition_occurrence_id,
    p.person_id,
    0                                             as condition_concept_id,
    cast(substr(c.start, 1, 10) as date)          as condition_start_date,
    cast(nullif(substr(c.stop, 1, 10), '') as date) as condition_end_date,
    32817                                         as condition_type_concept_id,
    c.code                                        as condition_source_value,
    0                                             as condition_source_concept_id,
    v.visit_occurrence_id
from c
inner join p on c.patient  = p.person_source_value
left  join v on c.encounter = v.visit_source_id
