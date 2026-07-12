"""REST API over the governed cohort operations — production-ready.

Features
--------
- Auth      : API key via X-API-Key header (optional, configured in .env)
- Rate limit: Per-IP sliding window (optional, configured in .env)
- Pagination: offset + limit on list endpoints
- Errors    : Structured JSON error responses, never raw tracebacks
- Logging   : Request timing + structured errors

Run:  make api   (uvicorn, http://localhost:8000/docs)
"""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request

from ..cohort import builder
from ..config import settings
from ..quality import run as quality_run
from .dependencies import (
    Pagination,
    paginator,
    rate_limit,
    require_api_key,
    warehouse_guard,
)
from .errors import APIError, register as register_errors

logger = logging.getLogger(__name__)

app = FastAPI(
    title="synthea-to-omop-fhir — Cohort API",
    description="Governed cohort queries over an OMOP CDM (synthetic patients).",
    version="0.2.0",
)
register_errors(app)


# ---------------------------------------------------------------------------
# Middleware: request logging + timing
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    logger.info(
        "%s %s — %s — %.2f ms",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    response.headers["X-Response-Time-Ms"] = f"{elapsed:.2f}"
    return response


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe — returns patient count if warehouse exists."""
    try:
        n = builder.total_patients()
        return {"status": "ok", "patients": n, "version": "0.2.0"}
    except Exception:
        return {"status": "degraded", "patients": None, "version": "0.2.0"}


@app.get("/ready", tags=["meta"])
def ready() -> dict:
    """Readiness probe — fails if warehouse is missing."""
    warehouse_guard()
    return {"status": "ready", "warehouse": str(settings.warehouse_db_abs)}


# ---------------------------------------------------------------------------
# Cohort (governed operations only)
# ---------------------------------------------------------------------------

@app.get("/cohort/prevalence", tags=["cohort"])
def prevalence(
    _auth: Annotated[None, Depends(require_api_key)],
    _rl: Annotated[None, Depends(rate_limit)],
    _wh: Annotated[None, Depends(warehouse_guard)],
    top_n: int = Query(10, ge=1, le=100),
    page: Annotated[Pagination, Depends(paginator)] = None,
) -> dict:
    """Most frequent conditions by distinct patient count (paginated)."""
    rows = builder.condition_prevalence(top_n)
    total = len(rows)
    paginated = rows[page.offset : page.offset + page.limit] if page else rows
    return {
        "data": paginated,
        "pagination": {
            "offset": page.offset if page else 0,
            "limit": page.limit if page else len(rows),
            "total": total,
        },
    }


@app.get("/cohort/condition", tags=["cohort"])
def condition(
    _auth: Annotated[None, Depends(require_api_key)],
    _rl: Annotated[None, Depends(rate_limit)],
    _wh: Annotated[None, Depends(warehouse_guard)],
    term: str = Query(..., min_length=2, examples=["lung cancer"]),
) -> dict:
    """Cohort of patients with a condition matching `term`, broken down by gender."""
    return builder.condition_cohort(term)


@app.get("/cohort/measurement", tags=["cohort"])
def measurement(
    _auth: Annotated[None, Depends(require_api_key)],
    _rl: Annotated[None, Depends(rate_limit)],
    _wh: Annotated[None, Depends(warehouse_guard)],
    term: str = Query(..., min_length=2, examples=["hemoglobin A1c"]),
) -> dict:
    """Summary statistics for measurements matching `term`."""
    return builder.measurement_summary(term)


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

@app.get("/quality", tags=["quality"])
def quality(
    _auth: Annotated[None, Depends(require_api_key)],
    _rl: Annotated[None, Depends(rate_limit)],
) -> dict:
    """Run health-grade data-quality checks over the OMOP CDM."""
    warehouse_guard()
    report = quality_run()
    return {
        "passed": report.passed,
        "summary": report.summary,
        "checks": [
            {
                "name": c.name,
                "table": c.table,
                "passed": c.passed,
                "n_violations": c.n_violations,
                "details": c.details,
            }
            for c in report.checks
        ],
    }
