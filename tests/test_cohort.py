"""Cohort operations — integration tests (need a built OMOP warehouse)."""

import pytest

from synthea_omop_fhir.cohort import builder
from synthea_omop_fhir.config import settings

needs_warehouse = pytest.mark.skipif(
    not settings.warehouse_db_abs.exists(),
    reason="Build the warehouse first (make warehouse).",
)


@needs_warehouse
def test_total_patients():
    assert builder.total_patients() > 0


@needs_warehouse
def test_condition_prevalence_shape():
    rows = builder.condition_prevalence(5)
    assert len(rows) == 5
    assert {"description", "patient_count"} <= set(rows[0])


@needs_warehouse
def test_condition_cohort_gender_breakdown():
    c = builder.condition_cohort("diabetes")
    assert c["patient_count"] > 0
    assert sum(c["by_gender"].values()) == c["patient_count"]


@needs_warehouse
def test_measurement_summary():
    m = builder.measurement_summary("Body Height")
    assert m["n"] > 0 and m["mean"] is not None
