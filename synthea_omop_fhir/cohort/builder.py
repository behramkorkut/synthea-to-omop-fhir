"""Governed cohort operations over the OMOP CDM.

On patient data, the rule is: NO free-form SQL. Callers (API, dashboard, or the
AI agent) may only invoke these parameterized, read-only operations. Every user
input is bound as a query parameter (never string-interpolated), so there is no
injection surface.
"""

from __future__ import annotations

from ..db import get_connection

# Distinct code -> description lookups (Synthea Bronze holds the human labels).
_COND_LABELS = "(SELECT DISTINCT code, description FROM omop.bronze.conditions)"
_OBS_LABELS = "(SELECT DISTINCT code, description FROM omop.bronze.observations)"


def _con():
    con = get_connection()
    con.set_schema("omop")
    return con


def total_patients() -> int:
    con = _con()
    try:
        return con.execute("SELECT count(*) FROM person").fetchone()[0]
    finally:
        con.close()


def condition_prevalence(top_n: int = 10) -> list[dict]:
    """Most frequent conditions by number of distinct patients."""
    top_n = max(1, min(int(top_n), 100))
    con = _con()
    try:
        rows = con.execute(
            f"SELECT c.description, count(DISTINCT co.person_id) AS n "
            f"FROM condition_occurrence co "
            f"JOIN {_COND_LABELS} c ON co.condition_source_value = c.code "
            f"GROUP BY c.description ORDER BY n DESC LIMIT ?",
            [top_n],
        ).fetchall()
        return [{"description": d, "patient_count": n} for d, n in rows]
    finally:
        con.close()


def condition_cohort(term: str) -> dict:
    """Cohort of patients having a condition whose label matches `term`."""
    con = _con()
    try:
        base = (
            f"WITH cohort AS ("
            f"  SELECT DISTINCT co.person_id "
            f"  FROM condition_occurrence co "
            f"  JOIN {_COND_LABELS} c ON co.condition_source_value = c.code "
            f"  WHERE lower(c.description) LIKE '%' || lower(?) || '%')"
        )
        count = con.execute(base + " SELECT count(*) FROM cohort", [term]).fetchone()[0]
        by_gender = con.execute(
            base + " SELECT p.gender_concept_id, count(*) "
            "FROM cohort JOIN person p USING (person_id) GROUP BY 1",
            [term],
        ).fetchall()
        genders = {8507: "male", 8532: "female"}
        gender = {genders.get(g, "unknown"): n for g, n in by_gender}
        return {"term": term, "patient_count": count, "by_gender": gender}
    finally:
        con.close()


def measurement_summary(term: str) -> dict:
    """Summary stats for measurements whose label matches `term` (e.g. 'HbA1c')."""
    con = _con()
    try:
        row = con.execute(
            f"SELECT count(*), avg(me.value_as_number), min(me.value_as_number), "
            f"max(me.value_as_number), any_value(me.unit_source_value) "
            f"FROM measurement me "
            f"JOIN {_OBS_LABELS} o ON me.measurement_source_value = o.code "
            f"WHERE lower(o.description) LIKE '%' || lower(?) || '%' "
            f"AND me.value_as_number IS NOT NULL",
            [term],
        ).fetchone()
        n, mean, lo, hi, unit = row
        return {
            "term": term,
            "n": n,
            "mean": round(mean, 2) if mean is not None else None,
            "min": lo,
            "max": hi,
            "unit": unit,
        }
    finally:
        con.close()
