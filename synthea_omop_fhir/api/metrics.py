"""Prometheus metrics for the cohort API.

Usage in FastAPI endpoints:
    from .metrics import REQUEST_COUNT, REQUEST_LATENCY

    REQUEST_COUNT.labels(method="GET", endpoint="/health", status="200").inc()
"""

from __future__ import annotations

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_COUNT = Counter(
    "api_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "api_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ERRORS_TOTAL = Counter(
    "api_errors_total",
    "Total API errors (handled exceptions)",
    ["error_code"],
)


def metrics_endpoint() -> Response:
    """Return Prometheus exposition format."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
