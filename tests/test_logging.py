"""Logging config tests (unit)."""

import logging

from synthea_omop_fhir.logging_config import _JsonFormatter, setup_logging


def test_json_formatter_outputs_valid_json():
    import json

    formatter = _JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    line = formatter.format(record)
    parsed = json.loads(line)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello"
    assert "timestamp" in parsed


def test_json_formatter_includes_correlation_id():
    import json

    formatter = _JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="warn",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "abc-123"
    line = formatter.format(record)
    parsed = json.loads(line)
    assert parsed["correlation_id"] == "abc-123"


def test_setup_logging_idempotent():
    """Calling setup_logging twice should not duplicate handlers."""
    setup_logging()
    root = logging.getLogger()
    n_handlers = len(root.handlers)
    setup_logging()
    assert len(root.handlers) == n_handlers
