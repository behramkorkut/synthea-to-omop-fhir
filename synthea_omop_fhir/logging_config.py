"""Structured logging configuration (JSON for production, text for dev)."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from .config import settings


class _JsonFormatter(logging.Formatter):
    """Format log records as newline-delimited JSON."""

    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "correlation_id"):
            out["correlation_id"] = record.correlation_id  # type: ignore[attr-defined]
        if record.exc_info:
            out["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


def setup_logging() -> None:
    """Configure root logger based on settings."""
    level = getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO)
    fmt = (settings.log_format or "text").lower()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root = logging.getLogger()
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(level)

    # noisy third-party libs -> WARNING
    for lib in ("duckdb", "httpx", "urllib3"):
        logging.getLogger(lib).setLevel(logging.WARNING)
