-- OMOP CDM: VISIT_OCCURRENCE
select
    visit_occurrence_id,
    person_id,
    visit_concept_id,
    visit_start_date,
    visit_end_date,
    visit_type_concept_id,
    visit_source_value
from {{ ref('stg_visit') }}
