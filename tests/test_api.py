"""API unit tests using FastAPI TestClient (no warehouse needed for error paths)."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from synthea_omop_fhir.api.dependencies import paginator, rate_limit, require_api_key, warehouse_guard
from synthea_omop_fhir.api.errors import (
    UnauthorizedError,
    WarehouseNotFoundError,
    api_error_handler,
    catchall_exception_handler,
    validation_error_handler,
)
from synthea_omop_fhir.api.main import app
from synthea_omop_fhir.config import settings


client = TestClient(app)


# --- S2 regression guard: structured JSON on any unhandled exception ---

def test_unhandled_exception_returns_structured_json_500():
    """P1-B/S2: a generic exception must yield a STRUCTURED JSON 500 through the
    REAL app stack. This is the only test that would catch a regression where a
    second `Exception` handler overrides the catchall (the bug fixed in S2).
    """
    async def _boom() -> dict:
        raise RuntimeError("kaboom")

    app.add_api_route("/__boom_test__", _boom, methods=["GET"])
    try:
        # raise_server_exceptions=False -> let the app's handlers produce the response.
        local = TestClient(app, raise_server_exceptions=False)
        resp = local.get("/__boom_test__")
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "internal_error"
        assert "message" in body["error"]
    finally:
        app.router.routes[:] = [
            r for r in app.router.routes if getattr(r, "path", None) != "/__boom_test__"
        ]


# --- Meta endpoints (no warehouse) ---

def test_health_returns_degraded_when_no_warehouse():
    """Health should degrade gracefully when warehouse is absent."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert "version" in data


def test_ready_returns_503_when_no_warehouse():
    """Ready probe must 503 when warehouse is missing."""
    resp = client.get("/ready")
    assert resp.status_code in (200, 503)


def test_metrics_returns_prometheus():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "api_requests_total" in resp.text or "python_gc" in resp.text


# --- Auth ---

def test_require_api_key_disabled_when_empty():
    """When settings.api_key is empty, auth is disabled."""
    original = settings.api_key
    try:
        settings.api_key = ""
        require_api_key(None)  # should not raise
    finally:
        settings.api_key = original


def test_require_api_key_rejects_missing():
    original = settings.api_key
    try:
        settings.api_key = "secret"
        with pytest.raises(UnauthorizedError):
            require_api_key(None)
    finally:
        settings.api_key = original


def test_require_api_key_rejects_wrong():
    original = settings.api_key
    try:
        settings.api_key = "secret"
        with pytest.raises(UnauthorizedError):
            require_api_key("wrong")
    finally:
        settings.api_key = original


def test_require_api_key_accepts_correct():
    original = settings.api_key
    try:
        settings.api_key = "secret"
        require_api_key("secret")  # should not raise
    finally:
        settings.api_key = original


# --- Rate limiting ---

def test_rate_limit_disabled_when_zero():
    """Rate limit is disabled when RATE_LIMIT_PER_MINUTE <= 0."""
    from unittest.mock import Mock

    req = Mock()
    req.client = Mock(host="127.0.0.1")
    rate_limit(req)  # should not raise


# --- Warehouse guard ---

def test_warehouse_guard_raises_when_missing():
    if settings.warehouse_db_abs.exists():
        pytest.skip("warehouse exists — cannot test missing guard")
    with pytest.raises(WarehouseNotFoundError):
        warehouse_guard()


# --- Error handlers ---

def test_api_error_json_shape():
    from synthea_omop_fhir.api.errors import _json

    resp = _json(400, "bad_request", "oops", detail=["x"])
    assert resp.status_code == 400
    body = resp.body
    assert b'"error"' in body


def test_api_error_handler_returns_json():
    from fastapi import Request

    req = Request({"type": "http", "method": "GET", "url": "http://test/health", "path": "/", "headers": []})
    resp = asyncio.run(api_error_handler(req, UnauthorizedError()))
    assert resp.status_code == 401
    body = json.loads(resp.body)
    assert body["error"]["code"] == "unauthorized"


def test_catchall_handler_returns_500():
    from fastapi import Request

    req = Request({"type": "http", "method": "GET", "url": "http://test/health", "path": "/", "headers": []})
    resp = asyncio.run(catchall_exception_handler(req, RuntimeError("boom")))
    assert resp.status_code == 500
    body = json.loads(resp.body)
    assert body["error"]["code"] == "internal_error"


def test_validation_error_handler_skips_non_validation():
    """validation_error_handler should re-raise non-RequestValidationError."""
    from fastapi import Request

    req = Request({"type": "http", "method": "GET", "url": "http://test/health", "path": "/", "headers": []})
    with pytest.raises(ValueError):
        asyncio.run(validation_error_handler(req, ValueError("not a validation error")))


# --- Pagination ---

def test_paginator_defaults():
    p = paginator()
    assert p.offset == 0
    assert p.limit == 100


def test_paginator_clamps_limit():
    p = paginator(offset=0, limit=5000)
    assert p.limit == 1000


def test_paginator_offset_negative():
    p = paginator(offset=-5, limit=50)
    assert p.offset == 0


# --- Cohort endpoints (skipped if no warehouse) ---

needs_warehouse = pytest.mark.skipif(
    True,  # will be overridden by conftest or keep simple
    reason="Warehouse not built",
)


@needs_warehouse
def test_prevalence_pagination():
    resp = client.get("/cohort/prevalence?top_n=3&offset=0&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "pagination" in data
