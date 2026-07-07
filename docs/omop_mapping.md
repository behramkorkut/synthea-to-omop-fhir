# OMOP mapping notes

## Approach: structure first, vocabulary second

The dbt models build the **OMOP CDM structure** faithfully — correct tables,
grain, surrogate keys, referential integrity — and preserve every source code in
`*_source_value`. The mapping to **standard `concept_id`s** is treated as an
explicit, separable step (as it is in every real OHDSI ETL).

### What is mapped now (deterministic, stable OMOP concepts)

Demographics use fixed OMOP standard concepts:

| Source | OMOP concept_id |
|---|---|
| gender M / F | 8507 / 8532 |
| race white / black / asian / native / hawaiian | 8527 / 8516 / 8515 / 8657 / 8557 |
| ethnicity hispanic / nonhispanic | 38003563 / 38003564 |

### What is left to the vocabulary step (`concept_id = 0`)

Clinical codes keep their **source vocabulary** but `*_concept_id = 0` (OMOP's
"No matching concept") until mapped:

| Synthea table | Source vocab | → OMOP table |
|---|---|---|
| conditions | SNOMED-CT | condition_occurrence |
| medications | RxNorm | drug_exposure |
| procedures | SNOMED-CT / CPT | procedure_occurrence |
| observations (numeric) | LOINC | measurement |
| observations (text) | LOINC | observation |

**Production mapping** = load the OHDSI vocabulary (CONCEPT, CONCEPT_RELATIONSHIP)
from [Athena](https://athena.ohdsi.org/) and resolve source → standard concepts
via `source_to_concept_map` / `CONCEPT_RELATIONSHIP` ("Maps to"). The reference
implementation is OHDSI's **ETL-Synthea**. This project keeps that step isolated
so it can be plugged in without touching the structure.

### Mapping coverage (a real data-quality metric)

We track the share of rows with a non-zero `concept_id` per domain — the same
idea as OHDSI's Data Quality Dashboard. Today it is 0% for clinical domains (by
design, pre-vocabulary) and 100% for demographics.
