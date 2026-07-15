#!/usr/bin/env python3
"""Apply a validated source_to_concept_map (STCM) to resolve concept_id = 0.

This script bridges the gap between synthea-to-omop-fhir (which produces
concept_id = 0 for unmapped codes) and governed-omop-rag (which produces a
human-validated source_to_concept_map). The update is idempotent: re-running
with the same STCM changes nothing.

Usage:
    uv run python scripts/apply_stcm.py --stcm data/source_to_concept_map.csv --db data/omop.duckdb
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb

from synthea_omop_fhir.config import settings
from synthea_omop_fhir.logging_config import configure_logging

logger = logging.getLogger(__name__)

# Domain tables and their source-code / concept-id columns
DOMAINS: dict[str, tuple[str, str]] = {
    "condition_occurrence": ("condition_source_value", "condition_concept_id"),
    "drug_exposure": ("drug_source_value", "drug_concept_id"),
    "measurement": ("measurement_source_value", "measurement_concept_id"),
    "procedure_occurrence": ("procedure_source_value", "procedure_concept_id"),
    "observation": ("observation_source_value", "observation_concept_id"),
}


def load_stcm(con: duckdb.DuckDBPyConnection, stcm_path: Path) -> int:
    """Load STCM CSV into a temporary DuckDB table; return row count."""
    con.execute(
        f"""
        CREATE OR REPLACE TABLE source_to_concept_map AS
        SELECT * FROM read_csv_auto('{stcm_path.as_posix()}')
        """
    )
    result = con.execute(
        "SELECT COUNT(*) FROM source_to_concept_map"
    ).fetchone()
    count = result[0] if result else 0
    logger.info("Loaded %d rows from %s", count, stcm_path)
    return count


def apply_domain(
    con: duckdb.DuckDBPyConnection,
    table: str,
    source_col: str,
    concept_col: str,
) -> int:
    """Update concept_id = 0 rows in *table* using the loaded STCM."""
    query = f"""
    UPDATE {table} AS t
    SET {concept_col} = m.target_concept_id
    FROM source_to_concept_map AS m
    WHERE t.{concept_col} = 0
      AND t.{source_col} = m.source_code
      AND m.source_vocabulary_id  = 'ICD10_FR'
      AND m.invalid_reason IS NULL
    """
    con.execute(query)
    result = con.execute(
        "SELECT changes()"
    ).fetchone()
    updated = result[0] if result else 0
    logger.info("Updated %d rows in %s", updated, table)
    return updated


def coverage_report(con: duckdb.DuckDBPyConnection) -> dict[str, float]:
    """Return unmapped ratio per domain table."""
    ratios: dict[str, float] = {}
    for table, (_, concept_col) in DOMAINS.items():
        total = con.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]
        unmapped = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {concept_col} = 0"
        ).fetchone()[0]
        ratio = (unmapped / total * 100) if total else 0.0
        ratios[table] = ratio
        logger.info(
            "%s.%s: %d/%d unmapped (%.1f%%)",
            table, concept_col, unmapped, total, ratio,
        )
    return ratios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply a validated STCM to resolve concept_id = 0."
    )
    parser.add_argument(
        "--stcm",
        type=Path,
        required=True,
        help="Path to source_to_concept_map.csv (validated by steward).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=settings.warehouse_db_abs,
        help="Path to OMOP DuckDB file (default: from config).",
    )
    args = parser.parse_args(argv)

    configure_logging()

    if not args.stcm.exists():
        logger.error("STCM file not found: %s", args.stcm)
        return 1

    con = duckdb.connect(str(args.db))
    try:
        load_stcm(con, args.stcm)
        total_updated = 0
        for table, (source_col, concept_col) in DOMAINS.items():
            total_updated += apply_domain(con, table, source_col, concept_col)

        logger.info("=== Coverage report after STCM application ===")
        coverage_report(con)
        logger.info("Total rows updated: %d", total_updated)
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
