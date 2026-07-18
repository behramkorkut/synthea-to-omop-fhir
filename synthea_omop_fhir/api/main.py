"""REST API over the governed cohort operations — production-ready.

Features
--------
- Auth      : API key via X-API-Key header (optional, configured in .env)
- Rate limit: Per-IP sliding window (optional, configured in .env)
- Pagination: offset + limit on list endpoints
- Errors    : Structured JSON error responses, never raw tracebacks
- Logging   : Structured JSON or text, with correlation IDs
- Metrics   : Prometheus exposition on /metrics

Run:  make api   (uvicorn, http://localhost:8000/docs)
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request, Response

from ..cohort import builder
from ..config import settings
from ..logging_config import setup_logging
from ..quality import run as quality_run
from .dependencies import (
    Pagination,
    paginator,
    rate_limit,
    require_api_key,
    warehouse_guard,
)
from .errors import register as register_errors
from .metrics import REQUEST_COUNT, REQUEST_LATENCY, metrics_endpoint

# Configure logging at import time so uvicorn workers inherit it.
setup_logging()

logger = logging.getLogger(__name__)

# Per-request correlation ID (propagated through logs).
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

app = FastAPI(
    title="synthea-to-omop-fhir — Cohort API",
    description="Governed cohort queries over an OMOP CDM (synthetic patients).",
    version="0.2.0",
)
register_errors(app)


# ---------------------------------------------------------------------------
# Middleware: correlation ID + structured request logging + metrics
# ---------------------------------------------------------------------------

@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-Id", str(uuid.uuid4()))
    _correlation_id.set(cid)

    start = time.time()
    try:
        response = await call_next(request)
    except Exception:
        # Ensure metrics are recorded even for unhandled exceptions.
        elapsed = time.time() - start
        path = request.url.path
        REQUEST_COUNT.labels(
            method=request.method, endpoint=path, status="500"
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method, endpoint=path
        ).observe(elapsed)
        raise

    elapsed = time.time() - start
    path = request.url.path
    status = str(response.status_code)

    REQUEST_COUNT.labels(
        method=request.method, endpoint=path, status=status
    ).inc()
    REQUEST_LATENCY.labels(
        method=request.method, endpoint=path
    ).observe(elapsed)

    extra = {"correlation_id": cid}
    logger.info(
        "%s %s — %s — %.2f ms",
        request.method,
        path,
        status,
        elapsed * 1000,
        extra=extra,
    )
    response.headers["X-Correlation-Id"] = cid
    response.headers["X-Response-Time-Ms"] = f"{elapsed * 1000:.2f}"
    return response


# Error metrics are incremented inside the catchall handlers (errors.py), which
# return the structured JSON response. Registering a second `Exception` handler
# here would OVERRIDE that catchall (Starlette keeps one handler per type) and,
# by re-raising, bypass the structured error contract — so we don't.


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness probe — returns patient count if warehouse is responsive."""
    try:
        start = time.time()
        n = builder.total_patients()
        latency_ms = (time.time() - start) * 1000
        return {
            "status": "ok",
            "patients": n,
            "db_latency_ms": round(latency_ms, 2),
            "version": "0.2.0",
        }
    except Exception:
        return {
            "status": "degraded",
            "patients": None,
            "db_latency_ms": None,
            "version": "0.2.0",
        }


@app.get("/ready", tags=["meta"])
def ready() -> dict:
    """Readiness probe — fails if warehouse is missing."""
    warehouse_guard()
    return {"status": "ready", "warehouse": str(settings.warehouse_db_abs)}


@app.get("/metrics", tags=["meta"])
def metrics() -> Response:
    """Prometheus metrics exposition."""
    return metrics_endpoint()


# ---------------------------------------------------------------------------
# Cohort (governed operations only)
# ---------------------------------------------------------------------------

@app.get("/cohort/prevalence", tags=["cohort"])
def prevalence(
    _auth: Annotated[None, Depends(require_api_key)],
    _rl: Annotated[None, Depends(rate_limit)],
    _wh: Annotated[None, Depends(warehouse_guard)],
    top_n: int = Query(10, ge=1, le=100),
    page: Annotated[Pagination | None, Depends(paginator)] = None,
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
