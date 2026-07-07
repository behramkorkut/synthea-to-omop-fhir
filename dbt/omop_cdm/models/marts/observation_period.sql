-- OMOP CDM: OBSERVATION_PERIOD (span of a person's records, from encounters)
with v as (
    select person_id, visit_start_date, visit_end_date from {{ ref('stg_visit') }}
)
select
    row_number() over (order by person_id) as observation_period_id,
    person_id,
    min(visit_start_date)                  as observation_period_start_date,
    max(visit_end_date)                    as observation_period_end_date,
    32817                                  as period_type_concept_id  -- EHR
from v
group by person_id
