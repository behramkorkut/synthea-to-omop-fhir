"""REST API over the governed cohort operations.

Run:  make api      (uvicorn, http://localhost:8000/docs)
Only exposes the parameterized cohort operations — never raw SQL.
"""

from __future__ import annotations

from fastapi import FastAPI, Query

from ..cohort import builder

app = FastAPI(
    title="synthea-to-omop-fhir — Cohort API",
    description="Governed cohort queries over an OMOP CDM (synthetic patients).",
    version="0.1.0",
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "patients": builder.total_patients()}


@app.get("/cohort/prevalence", tags=["cohort"])
def prevalence(top_n: int = Query(10, ge=1, le=100)) -> list[dict]:
    """Most frequent conditions by distinct patient count."""
    return builder.condition_prevalence(top_n)


@app.get("/cohort/condition", tags=["cohort"])
def condition(term: str = Query(..., min_length=2, examples=["lung cancer"])) -> dict:
    """Cohort of patients with a condition matching `term`, broken down by gender."""
    return builder.condition_cohort(term)


@app.get("/cohort/measurement", tags=["cohort"])
def measurement(term: str = Query(..., min_length=2, examples=["hemoglobin A1c"])) -> dict:
    """Summary statistics for measurements matching `term`."""
    return builder.measurement_summary(term)
