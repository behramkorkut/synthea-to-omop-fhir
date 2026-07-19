"""Health-grade data-quality checks over the OMOP CDM (Pandera + DuckDB).

Inspired by OHDSI DataQualityDashboard (DQD): validate types, nullability,
business coherence, and mapping coverage. Run:

    uv run python -m synthea_omop_fhir.quality.run
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field

from typing import Any

import pandas as pd
import pandera as pa
from pandera import Column, DataFrameSchema

from ..config import settings
from ..db import get_connection
from ..sql import quote_ident


@dataclass
class CheckResult:
    name: str
    table: str
    passed: bool
    n_violations: int = 0
    details: list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    passed: bool
    checks: list[CheckResult]
    summary: dict


# ---------------------------------------------------------------------------
# Pandera schemas — OMOP CDM column contracts
# ---------------------------------------------------------------------------

PERSON_SCHEMA = DataFrameSchema(
    {
        "person_id": Column(int, nullable=False, unique=True),
        "gender_concept_id": Column(
            int, nullable=False, checks=pa.Check.isin([8507, 8532, 0])
        ),
        "year_of_birth": Column(int, nullable=False),
        "month_of_birth": Column(
            int, nullable=True, checks=pa.Check.isin(list(range(1, 13)))
        ),
        "day_of_birth": Column(
            int, nullable=True, checks=pa.Check.isin(list(range(1, 32)))
        ),
        "person_source_value": Column(str, nullable=False),
    },
    strict=False,
    coerce=True,
)

VISIT_SCHEMA = DataFrameSchema(
    {
        "visit_occurrence_id": Column(int, nullable=False, unique=True),
        "person_id": Column(int, nullable=False),
        "visit_concept_id": Column(
            int, nullable=False, checks=pa.Check.isin([9201, 9202, 9203])
        ),
        "visit_start_date": Column(pa.Date, nullable=False),
        "visit_end_date": Column(pa.Date, nullable=True),
    },
    strict=False,
    coerce=True,
)

CONDITION_SCHEMA = DataFrameSchema(
    {
        "condition_occurrence_id": Column(int, nullable=False, unique=True),
        "person_id": Column(int, nullable=False),
        "condition_start_date": Column(pa.Date, nullable=False),
        "condition_end_date": Column(pa.Date, nullable=True),
    },
    strict=False,
    coerce=True,
)

MEASUREMENT_SCHEMA = DataFrameSchema(
    {
        "measurement_id": Column(int, nullable=False, unique=True),
        "person_id": Column(int, nullable=False),
        "measurement_date": Column(pa.Date, nullable=False),
        "value_as_number": Column(float, nullable=True),
    },
    strict=False,
    coerce=True,
)

DRUG_SCHEMA = DataFrameSchema(
    {
        "drug_exposure_id": Column(int, nullable=False, unique=True),
        "person_id": Column(int, nullable=False),
        "drug_exposure_start_date": Column(pa.Date, nullable=False),
        "drug_exposure_end_date": Column(pa.Date, nullable=True),
    },
    strict=False,
    coerce=True,
)

SCHEMAS: dict[str, DataFrameSchema] = {
    "person": PERSON_SCHEMA,
    "visit_occurrence": VISIT_SCHEMA,
    "condition_occurrence": CONDITION_SCHEMA,
    "measurement": MEASUREMENT_SCHEMA,
    "drug_exposure": DRUG_SCHEMA,
}


# ---------------------------------------------------------------------------
# Custom coherence checks (beyond Pandera schemas)
# ---------------------------------------------------------------------------


def _check_death_after_birth(con: Any) -> CheckResult:
    rows = con.execute(
        "SELECT person_id FROM person p "
        "JOIN death d USING (person_id) "
        "WHERE d.death_date < p.birth_datetime"
    ).fetchall()
    return CheckResult(
        name="death_after_birth",
        table="death",
        passed=len(rows) == 0,
        n_violations=len(rows),
        details=[f"person_id={r[0]}" for r in rows[:5]],
    )


def _check_visit_end_after_start(con: Any) -> CheckResult:
    rows = con.execute(
        "SELECT visit_occurrence_id FROM visit_occurrence "
        "WHERE visit_end_date IS NOT NULL AND visit_end_date < visit_start_date"
    ).fetchall()
    return CheckResult(
        name="visit_end_after_start",
        table="visit_occurrence",
        passed=len(rows) == 0,
        n_violations=len(rows),
        details=[f"visit_occurrence_id={r[0]}" for r in rows[:5]],
    )


def _check_condition_end_after_start(con: Any) -> CheckResult:
    rows = con.execute(
        "SELECT condition_occurrence_id FROM condition_occurrence "
        "WHERE condition_end_date IS NOT NULL AND condition_end_date < condition_start_date"
    ).fetchall()
    return CheckResult(
        name="condition_end_after_start",
        table="condition_occurrence",
        passed=len(rows) == 0,
        n_violations=len(rows),
        details=[f"condition_occurrence_id={r[0]}" for r in rows[:5]],
    )


def _check_drug_end_after_start(con: Any) -> CheckResult:
    """End ≥ start on drug exposures.

    Distinguishes incoherences **introduced by the pipeline** (a real defect →
    FAIL) from those **inherited from the Synthea source** (`bronze.medications`
    already has stop < start), which the pipeline preserves faithfully by design.
    Source-inherited quirks are reported (counted + listed) but not treated as a
    pipeline failure — the same informational stance as `mapping_coverage`.
    """
    n_out = con.execute(
        "SELECT count(*) FROM drug_exposure "
        "WHERE drug_exposure_end_date IS NOT NULL "
        "AND drug_exposure_end_date < drug_exposure_start_date"
    ).fetchone()[0]
    try:
        n_source = con.execute(
            "SELECT count(*) FROM bronze.medications "
            "WHERE stop IS NOT NULL AND stop <> '' AND stop < start"
        ).fetchone()[0]
    except Exception:
        n_source = 0
    pipeline_introduced = max(0, n_out - n_source)
    return CheckResult(
        name="drug_end_after_start",
        table="drug_exposure",
        passed=pipeline_introduced == 0,  # green if all quirks come from source
        n_violations=n_out,
        details=[
            f"{n_out} end<start total; {n_source} inherited from Synthea source "
            f"(bronze.medications), {pipeline_introduced} introduced by the pipeline.",
        ],
    )


# LOINC codes where a value ≤ 0 is physiologically impossible. Scoped on purpose:
# many valid measurements are legitimately 0 or negative (questionnaire/severity
# scores, DALY/QALY, urine dipstick "presence" flags…), so a blanket
# "value ≤ 0 is a violation" rule produces thousands of false positives.
_POSITIVE_MEASUREMENT_CODES = (
    "8302-2",  # Body height
    "29463-7",  # Body weight
    "39156-5",  # Body mass index (BMI)
    "8310-5",  # Body temperature
    "8867-4",  # Heart rate
)


def _check_measurement_positive_value(con: Any) -> CheckResult:
    """Physical measurements (height, weight, BMI, temperature, heart rate) must
    be strictly positive. Scoped to those LOINC codes — see note above."""
    placeholders = ", ".join("?" for _ in _POSITIVE_MEASUREMENT_CODES)
    rows = con.execute(
        "SELECT measurement_id FROM measurement "
        f"WHERE measurement_source_value IN ({placeholders}) "
        "AND value_as_number IS NOT NULL AND value_as_number <= 0",
        list(_POSITIVE_MEASUREMENT_CODES),
    ).fetchall()
    return CheckResult(
        name="measurement_positive_value",
        table="measurement",
        passed=len(rows) == 0,
        n_violations=len(rows),
        details=[f"measurement_id={r[0]}" for r in rows[:5]],
    )


# ---------------------------------------------------------------------------
# Mapping coverage check (concept_id = 0)
# ---------------------------------------------------------------------------


def _check_mapping_coverage(con: Any) -> CheckResult:
    """Report % of records with unmapped concept_id (= 0)."""
    tables = [
        ("person", "gender_concept_id"),
        ("visit_occurrence", "visit_concept_id"),
        ("condition_occurrence", "condition_concept_id"),
        ("drug_exposure", "drug_concept_id"),
        ("measurement", "measurement_concept_id"),
        ("procedure_occurrence", "procedure_concept_id"),
        ("observation", "observation_concept_id"),
    ]
    details: list[str] = []
    total_zero = 0
    total_rows = 0
    for table, col in tables:
        try:
            n_total, n_zero = con.execute(
                f"SELECT count(*), count(*) FILTER (WHERE {quote_ident(col)} = 0) "
                f"FROM {quote_ident(table)}"
            ).fetchone()
            total_rows += n_total
            total_zero += n_zero
            pct = (n_zero / n_total * 100) if n_total else 0
            details.append(f"{table}.{col}: {n_zero}/{n_total} unmapped ({pct:.1f}%)")
        except Exception:
            details.append(f"{table}.{col}: table or column not found — skipped")
    overall_pct = (total_zero / total_rows * 100) if total_rows else 0
    # We consider it a warning, not a hard failure (mapping is external).
    return CheckResult(
        name="mapping_coverage",
        table="omop",
        passed=True,  # informational
        n_violations=total_zero,
        details=details
        + [f"OVERALL unmapped: {total_zero}/{total_rows} ({overall_pct:.1f}%)"],
    )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


def _load_df(con, table: str) -> pd.DataFrame:
    return con.execute(f"SELECT * FROM {table}").fetchdf()


def run() -> QualityReport:
    db_path = settings.warehouse_db_abs
    if not db_path.exists():
        raise FileNotFoundError(
            f"OMOP warehouse not found at {db_path}. Run `make omop` first."
        )

    con = get_connection()
    con.set_schema("omop")

    checks: list[CheckResult] = []

    # --- Pandera schema checks ---
    for table, schema in SCHEMAS.items():
        try:
            df = _load_df(con, table)
            if df.empty:
                checks.append(
                    CheckResult(
                        name=f"schema_{table}",
                        table=table,
                        passed=True,
                        details=["empty table"],
                    )
                )
                continue
            schema.validate(df, lazy=True)
            checks.append(
                CheckResult(
                    name=f"schema_{table}", table=table, passed=True, n_violations=0
                )
            )
        except pa.errors.SchemaErrors as exc:
            details = []
            for err in exc.schema_errors[:5]:
                msg = getattr(err, "error", str(err))
                details.append(msg)
            checks.append(
                CheckResult(
                    name=f"schema_{table}",
                    table=table,
                    passed=False,
                    n_violations=len(exc.schema_errors),
                    details=details,
                )
            )
        except Exception as exc:
            checks.append(
                CheckResult(
                    name=f"schema_{table}",
                    table=table,
                    passed=False,
                    details=[str(exc)],
                )
            )

    # --- Coherence checks ---
    checks.append(_check_death_after_birth(con))
    checks.append(_check_visit_end_after_start(con))
    checks.append(_check_condition_end_after_start(con))
    checks.append(_check_drug_end_after_start(con))
    checks.append(_check_measurement_positive_value(con))

    # --- Mapping coverage ---
    checks.append(_check_mapping_coverage(con))

    con.close()

    passed = all(c.passed for c in checks)
    # On sépare les VRAIES violations (checks en échec) des constats
    # INFORMATIONNELS (checks verts qui comptent tout de même des cas : couverture
    # de mapping, incohérences héritées de la source). Auparavant `total_violations`
    # mélangeait les deux, affichant ~1 M sur un rapport 100 % vert (trompeur).
    summary = {
        "total_checks": len(checks),
        "passed": sum(1 for c in checks if c.passed),
        "failed": sum(1 for c in checks if not c.passed),
        "violations": sum(c.n_violations for c in checks if not c.passed),
        "informational_findings": sum(c.n_violations for c in checks if c.passed),
    }
    return QualityReport(passed=passed, checks=checks, summary=summary)


def main() -> None:
    report = run()
    print(json.dumps(asdict(report), indent=2, default=str))
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
