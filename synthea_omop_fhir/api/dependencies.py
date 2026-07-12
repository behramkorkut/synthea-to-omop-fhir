"""FastAPI dependencies: auth, pagination, database, rate limiting."""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Annotated

from fastapi import Header, Query, Request

from ..config import settings
from .errors import RateLimitError, UnauthorizedError, WarehouseNotFoundError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    """Reject if an API key is configured and the header is missing/invalid."""
    expected = settings.api_key
    if not expected:
        return  # auth disabled in demo mode
    if x_api_key is None:
        raise UnauthorizedError()
    import secrets
    if not secrets.compare_digest(x_api_key, expected):
        raise UnauthorizedError()


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class Pagination:
    def __init__(self, offset: int = 0, limit: int = 100) -> None:
        self.offset = max(0, offset)
        self.limit = max(1, min(limit, 1000))


def paginator(
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> Pagination:
    return Pagination(offset=offset, limit=limit)


# ---------------------------------------------------------------------------
# Rate limiting (simple in-memory per-IP)
# ---------------------------------------------------------------------------

_MAX_REQ = settings.rate_limit_per_minute
_WINDOW_SEC = 60

_buckets: dict[str, deque[float]] = {}


def rate_limit(request: Request) -> None:
    if _MAX_REQ <= 0:
        return  # disabled
    client = request.client.host if request.client else "unknown"
    now = time.time()
    bucket = _buckets.setdefault(client, deque())
    # evict old entries
    while bucket and bucket[0] < now - _WINDOW_SEC:
        bucket.popleft()
    if len(bucket) >= _MAX_REQ:
        raise RateLimitError()
    bucket.append(now)


# ---------------------------------------------------------------------------
# Warehouse guard
# ---------------------------------------------------------------------------

def warehouse_guard() -> None:
    if not settings.warehouse_db_abs.exists():
        raise WarehouseNotFoundError()
