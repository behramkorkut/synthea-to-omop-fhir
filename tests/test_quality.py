"""Quality module tests (unit, no warehouse)."""

import pytest
import pandera as pa

from synthea_omop_fhir.quality.run import (
    PERSON_SCHEMA,
    CheckResult,
    QualityReport,
)


def test_check_result_defaults():
    c = CheckResult(name="test", table="person", passed=True)
    assert c.n_violations == 0
    assert c.details == []


def test_quality_report_summary():
    checks = [
        CheckResult(name="a", table="t", passed=True),
        CheckResult(name="b", table="t", passed=False, n_violations=3),
    ]
    r = QualityReport(passed=False, checks=checks, summary={})
    assert not r.passed


def test_person_schema_accepts_valid():
    import pandas as pd

    df = pd.DataFrame({
        "person_id": [1, 2],
        "gender_concept_id": [8507, 8532],
        "year_of_birth": [1980, 1990],
        "month_of_birth": [1, 12],
        "day_of_birth": [15, 30],
        "person_source_value": ["p1", "p2"],
    })
    validated = PERSON_SCHEMA.validate(df, lazy=True)
    assert validated is not None


def test_person_schema_rejects_invalid_gender():
    import pandas as pd

    df = pd.DataFrame({
        "person_id": [1],
        "gender_concept_id": [9999],  # invalid
        "year_of_birth": [1980],
        "month_of_birth": [1],
        "day_of_birth": [15],
        "person_source_value": ["p1"],
    })
    with pytest.raises(pa.errors.SchemaErrors):
        PERSON_SCHEMA.validate(df, lazy=True)
