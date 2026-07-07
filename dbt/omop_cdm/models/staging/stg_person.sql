-- Silver: one row per patient, with the OMOP surrogate person_id and the
-- exact demographic concept mappings (gender / race / ethnicity are stable
-- OMOP standard concepts, so we map them directly).
with src as (
    select * from {{ source('bronze', 'patients') }}
)

select
    row_number() over (order by id)              as person_id,
    id                                           as person_source_value,
    cast(birthdate as date)                      as birth_date,
    cast(nullif(deathdate, '') as date)          as death_date,

    -- gender
    gender                                        as gender_source_value,
    case upper(gender)
        when 'M' then 8507  -- MALE
        when 'F' then 8532  -- FEMALE
        else 0
    end                                          as gender_concept_id,

    -- race (OMOP standard race concepts)
    race                                          as race_source_value,
    case lower(race)
        when 'white'    then 8527
        when 'black'    then 8516
        when 'asian'    then 8515
        when 'native'   then 8657   -- American Indian / Alaska Native
        when 'hawaiian' then 8557   -- Native Hawaiian / Other Pacific Islander
        else 0
    end                                          as race_concept_id,

    -- ethnicity
    ethnicity                                     as ethnicity_source_value,
    case lower(ethnicity)
        when 'hispanic'    then 38003563
        when 'nonhispanic' then 38003564
        else 0
    end                                          as ethnicity_concept_id
from src
