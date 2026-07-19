"""Database abstraction layer: DuckDB (demo)  ↔  PostgreSQL (prod).

Usage
-----
    from synthea_omop_fhir.db import get_connection
    con = get_connection()
    con.set_schema("omop")
    rows = con.execute("SELECT * FROM person").fetchall()
    con.close()

Prod
----
Install the psycopg driver:
    uv add psycopg[binary]

Then set in `.env`:
    DB_ENGINE=postgres
    POSTGRES_DSN=postgresql://user:pass@host:5432/omop
"""

from __future__ import annotations

import importlib.util
from typing import Any

from .config import settings


class Connection:
    """Minimal DB-API wrapper that works for both DuckDB and PostgreSQL."""

    def __init__(self, raw: Any, engine: str) -> None:
        self._raw = raw
        self._engine = engine

    def set_schema(self, name: str) -> None:
        """Set the default schema for the session.

        `name` is an internal constant (never user input). We still validate it
        as a SQL identifier and quote it, so this is not an injection surface.
        """
        if not name.isidentifier():
            raise ValueError(f"Invalid schema name: {name!r}")
        if self._engine == "duckdb":
            # The DuckDB catalog is named after the *file* (e.g. a renamed
            # WAREHOUSE_DB → different catalog), so we resolve it at runtime
            # instead of assuming it equals the schema name.
            catalog = self._raw.execute("SELECT current_database()").fetchone()[0]
            self._raw.execute(f'USE "{catalog}"."{name}"')
        elif self._engine == "postgres":
            # SET does not accept bound parameters for an identifier; quote it.
            self._raw.execute(f'SET search_path TO "{name}"')
        else:
            raise ValueError(f"Unknown engine: {self._engine}")

    def execute(self, sql: str, params: Any = None) -> "Connection":
        if self._engine == "postgres" and params is not None:
            # psycopg uses %(name)s for dicts or positional markers
            self._raw.execute(sql, params)
        else:
            if params is not None:
                self._raw.execute(sql, params)
            else:
                self._raw.execute(sql)
        return self

    def fetchall(self) -> list:
        return self._raw.fetchall()

    def fetchone(self) -> Any:
        return self._raw.fetchone()

    def fetchdf(self) -> Any:
        """Return a pandas DataFrame (DuckDB native or via pandas for PostgreSQL)."""
        if self._engine == "duckdb":
            return self._raw.fetchdf()
        # PostgreSQL fallback: read the last cursor into a DataFrame
        import pandas as pd

        cur = self._raw
        return pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])

    def close(self) -> None:
        self._raw.close()


class _PostgresConnection(Connection):
    """psycopg-specific wrapper (auto-commit, dict params)."""

    def __init__(self, raw: Any) -> None:
        super().__init__(raw, "postgres")
        raw.autocommit = True

    def execute(self, sql: str, params: Any = None) -> "_PostgresConnection":
        if params is not None:
            self._raw.execute(sql, params)
        else:
            self._raw.execute(sql)
        return self


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_connection() -> Connection:
    """Return a connection appropriate for the configured engine."""
    engine = (settings.db_engine or "duckdb").lower()
    if engine == "duckdb":
        import duckdb

        return Connection(duckdb.connect(str(settings.warehouse_db_abs)), "duckdb")
    if engine == "postgres":
        if importlib.util.find_spec("psycopg") is None:
            raise RuntimeError(
                "psycopg is not installed. Run: uv add 'psycopg[binary]'"
            )
        import psycopg

        dsn = settings.postgres_dsn
        if not dsn:
            raise RuntimeError("POSTGRES_DSN is not set. Add it to your .env.")
        return _PostgresConnection(psycopg.connect(dsn))
    raise ValueError(f"Unsupported DB_ENGINE: {engine}")
