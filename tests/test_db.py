"""DB abstraction layer tests (unit, no warehouse)."""

import pytest

from synthea_omop_fhir.config import settings
from synthea_omop_fhir.db import Connection, _PostgresConnection, get_connection


class FakeRaw:
    """Minimal fake for Connection tests."""

    def __init__(self):
        self.calls = []
        self._rows = []
        self._description = []
        self.autocommit = False

    @property
    def description(self):
        return self._description

    def execute(self, sql, params=None):
        self.calls.append(("execute", sql, params))
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        # DuckDB set_schema resolves the catalog via SELECT current_database().
        if self.calls and "current_database" in str(self.calls[-1]):
            return ("omop",)
        return self._rows[0] if self._rows else None

    def fetchdf(self):
        import pandas as pd
        return pd.DataFrame(self._rows)

    def close(self):
        self.calls.append("close")


def test_duckdb_set_schema():
    raw = FakeRaw()
    con = Connection(raw, "duckdb")
    con.set_schema("omop")
    # Catalog resolved at runtime (filename-independent), schema quoted.
    assert any("current_database" in str(c) for c in raw.calls)
    assert any('"omop"."omop"' in str(c) for c in raw.calls)


def test_postgres_set_schema():
    raw = FakeRaw()
    con = Connection(raw, "postgres")
    con.set_schema("omop")
    assert any('SET search_path TO "omop"' in str(c) for c in raw.calls)


def test_set_schema_rejects_non_identifier():
    raw = FakeRaw()
    con = Connection(raw, "duckdb")
    with pytest.raises(ValueError, match="Invalid schema name"):
        con.set_schema("omop; DROP TABLE person")


def test_connection_set_schema_unknown_engine():
    raw = FakeRaw()
    con = Connection(raw, "sqlite")
    with pytest.raises(ValueError, match="Unknown engine"):
        con.set_schema("omop")


def test_connection_execute_with_params():
    raw = FakeRaw()
    con = Connection(raw, "duckdb")
    con.execute("SELECT * FROM person WHERE id = ?", [1])
    assert raw.calls[0] == ("execute", "SELECT * FROM person WHERE id = ?", [1])


def test_connection_fetchall():
    raw = FakeRaw()
    raw._rows = [(1, "male"), (2, "female")]
    con = Connection(raw, "duckdb")
    assert con.execute("SELECT * FROM person").fetchall() == [(1, "male"), (2, "female")]


def test_connection_fetchone():
    raw = FakeRaw()
    raw._rows = [(1, "male")]
    con = Connection(raw, "duckdb")
    assert con.execute("SELECT * FROM person").fetchone() == (1, "male")


def test_connection_fetchone_empty():
    raw = FakeRaw()
    con = Connection(raw, "duckdb")
    assert con.execute("SELECT * FROM person").fetchone() is None


def test_connection_close():
    raw = FakeRaw()
    con = Connection(raw, "duckdb")
    con.close()
    assert "close" in raw.calls


# --- Factory ---

def test_get_connection_returns_connection():
    """When db_engine is duckdb and warehouse exists, get_connection works."""
    original = settings.db_engine
    settings.db_engine = "duckdb"
    try:
        con = get_connection()
        assert isinstance(con, Connection)
        con.close()
    finally:
        settings.db_engine = original


def test_get_connection_rejects_unsupported_engine():
    original = settings.db_engine
    settings.db_engine = "mysql"
    try:
        with pytest.raises(ValueError, match="Unsupported"):
            get_connection()
    finally:
        settings.db_engine = original


def test_get_connection_postgres_missing_psycopg():
    """If psycopg is not installed, should raise RuntimeError."""
    import importlib.util

    original = settings.db_engine
    settings.db_engine = "postgres"
    try:
        # If psycopg is NOT installed, this raises RuntimeError
        if importlib.util.find_spec("psycopg") is None:
            with pytest.raises(RuntimeError, match="psycopg is not installed"):
                get_connection()
    finally:
        settings.db_engine = original


def test_get_connection_postgres_missing_dsn():
    """If postgres_dsn is empty, should raise RuntimeError."""
    import importlib.util

    original = settings.db_engine
    original_dsn = settings.postgres_dsn
    settings.db_engine = "postgres"
    settings.postgres_dsn = ""
    try:
        # Only test if psycopg IS installed (otherwise it raises the "not installed" error first)
        if importlib.util.find_spec("psycopg") is not None:
            with pytest.raises(RuntimeError, match="POSTGRES_DSN is not set"):
                get_connection()
    finally:
        settings.db_engine = original
        settings.postgres_dsn = original_dsn


# --- _PostgresConnection ---

def test_postgres_connection_autocommit():
    raw = FakeRaw()
    raw.autocommit = False
    con = _PostgresConnection(raw)
    assert raw.autocommit is True
    assert con._engine == "postgres"


def test_postgres_connection_execute_with_params():
    raw = FakeRaw()
    con = _PostgresConnection(raw)
    con.execute("SELECT * FROM person WHERE id = %s", (1,))
    assert raw.calls[0] == ("execute", "SELECT * FROM person WHERE id = %s", (1,))


def test_postgres_connection_fetchdf():
    raw = FakeRaw()
    raw._rows = [{"a": 1}, {"a": 2}]
    raw._description = [type("Col", (), {"name": "a"})()]
    con = _PostgresConnection(raw)
    df = con.execute("SELECT * FROM person").fetchdf()
    assert len(df) == 2
    assert list(df.columns) == ["a"]


# --- Connection.fetchdf ---

def test_connection_fetchdf_duckdb():
    raw = FakeRaw()
    raw._rows = [(1, "male"), (2, "female")]
    con = Connection(raw, "duckdb")
    df = con.execute("SELECT * FROM person").fetchdf()
    assert len(df) == 2


def test_connection_fetchdf_postgres():
    raw = FakeRaw()
    raw._rows = [(1, "male"), (2, "female")]
    raw._description = [type("Col", (), {"name": "id"})(), type("Col", (), {"name": "gender"})()]
    con = Connection(raw, "postgres")
    df = con.execute("SELECT * FROM person").fetchdf()
    assert len(df) == 2
    assert list(df.columns) == ["id", "gender"]