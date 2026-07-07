-- Silver: one row per encounter, with the OMOP surrogate visit_occurrence_id,
-- the resolved person_id, and the encounter class mapped to an OMOP visit concept.
with enc as (
    select * from {{ source('bronze', 'encounters') }}
),
person as (
    select person_id, person_source_value from {{ ref('stg_person') }}
)

select
    row_number() over (order by enc.id)          as visit_occurrence_id,
    enc.id                                        as visit_source_id,      -- UUID, for joins
    person.person_id,
    cast(enc.start as timestamp)::date            as visit_start_date,
    coalesce(cast(nullif(enc.stop, '') as timestamp)::date,
             cast(enc.start as timestamp)::date)  as visit_end_date,
    enc.encounterclass                            as visit_source_value,
    case lower(enc.encounterclass)
        when 'inpatient'  then 9201  -- Inpatient Visit
        when 'emergency'  then 9203  -- Emergency Room Visit
        when 'urgentcare' then 9203
        else 9202                    -- Outpatient Visit (ambulatory, wellness, etc.)
    end                                           as visit_concept_id,
    32817                                         as visit_type_concept_id  -- EHR
from enc
inner join person on enc.patient = person.person_source_value
