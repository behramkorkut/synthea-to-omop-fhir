"""Quality module tests (unit, no warehouse)."""

import duckdb
import pytest
import pandera as pa

from synthea_omop_fhir.quality.run import (
    PERSON_SCHEMA,
    CheckResult,
    QualityReport,
    _check_drug_end_after_start,
    _check_measurement_positive_value,
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

    df = pd.DataFrame(
        {
            "person_id": [1, 2],
            "gender_concept_id": [8507, 8532],
            "year_of_birth": [1980, 1990],
            "month_of_birth": [1, 12],
            "day_of_birth": [15, 30],
            "person_source_value": ["p1", "p2"],
        }
    )
    validated = PERSON_SCHEMA.validate(df, lazy=True)
    assert validated is not None


def test_person_schema_rejects_invalid_gender():
    import pandas as pd

    df = pd.DataFrame(
        {
            "person_id": [1],
            "gender_concept_id": [9999],  # invalid
            "year_of_birth": [1980],
            "month_of_birth": [1],
            "day_of_birth": [15],
            "person_source_value": ["p1"],
        }
    )
    with pytest.raises(pa.errors.SchemaErrors):
        PERSON_SCHEMA.validate(df, lazy=True)


def test_measurement_positive_check_is_scoped_to_physical_codes():
    """S3: a score legitimately at 0 is NOT a violation; only physical codes are."""
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE measurement (measurement_id INT, measurement_source_value VARCHAR, "
        "value_as_number DOUBLE)"
    )
    con.execute(
        "INSERT INTO measurement VALUES "
        "(1, '72514-3', 0),   -- pain score 0/10: valid, must NOT be flagged\n"
        "(2, '8302-2', 0),    -- body height 0: impossible, MUST be flagged\n"
        "(3, '29463-7', 70)   -- body weight 70: valid"
    )
    result = _check_measurement_positive_value(con)
    con.close()
    assert result.n_violations == 1  # only the height=0, not the pain score
    assert not result.passed


def test_drug_end_check_ignores_source_inherited_incoherence():
    """S4: an end<start inherited from bronze source is reported but not a FAIL."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA bronze")
    con.execute("CREATE TABLE bronze.medications (start VARCHAR, stop VARCHAR)")
    con.execute("INSERT INTO bronze.medications VALUES ('2020-01-10', '2020-01-05')")
    con.execute(
        "CREATE TABLE drug_exposure (drug_exposure_id INT, "
        "drug_exposure_start_date DATE, drug_exposure_end_date DATE)"
    )
    con.execute(
        "INSERT INTO drug_exposure VALUES (1, DATE '2020-01-10', DATE '2020-01-05')"
    )
    result = _check_drug_end_after_start(con)
    con.close()
    assert result.n_violations == 1  # still counted and reported
    assert result.passed  # but green: the quirk is source-inherited


def test_drug_end_check_fails_on_pipeline_introduced_incoherence():
    """P1-B: if the source is CLEAN but drug_exposure is incoherent, the check
    must FAIL — the incoherence was introduced by the pipeline, not inherited."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA bronze")
    con.execute("CREATE TABLE bronze.medications (start VARCHAR, stop VARCHAR)")
    # Source propre : stop >= start.
    con.execute("INSERT INTO bronze.medications VALUES ('2020-01-01', '2020-01-10')")
    con.execute(
        "CREATE TABLE drug_exposure (drug_exposure_id INT, "
        "drug_exposure_start_date DATE, drug_exposure_end_date DATE)"
    )
    # Sortie incohérente alors que la source ne l'était pas.
    con.execute(
        "INSERT INTO drug_exposure VALUES (1, DATE '2020-01-10', DATE '2020-01-05')"
    )
    result = _check_drug_end_after_start(con)
    con.close()
    assert result.n_violations == 1
    assert not result.passed  # introduite par le pipeline -> FAIL


def test_drug_end_check_fails_when_bronze_missing():
    """Fail-safe : sans schéma bronze, on ne peut pas attribuer -> FAIL prudent."""
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE drug_exposure (drug_exposure_id INT, "
        "drug_exposure_start_date DATE, drug_exposure_end_date DATE)"
    )
    con.execute(
        "INSERT INTO drug_exposure VALUES (1, DATE '2020-01-10', DATE '2020-01-05')"
    )
    result = _check_drug_end_after_start(con)
    con.close()
    assert result.n_violations == 1
    assert not result.passed
