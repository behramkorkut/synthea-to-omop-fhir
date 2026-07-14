"""Load the Synthea CSV export into DuckDB, schema `bronze`.

Bronze = raw ingestion. We load every column as VARCHAR (raw text) and do NOT
clean, cast or reshape anything here. Typing, cleaning and the OMOP mapping are
the job of the dbt Silver/Gold layers — so Bronze stays rebuildable from source.

Run:  uv run python -m synthea_omop_fhir.load_bronze
"""

from __future__ import annotations

from .config import settings
from .db import get_connection

# The Synthea tables we ingest (all of them, so nothing is lost for later use).
SYNTHEA_TABLES = [
    "patients", "encounters", "conditions", "medications", "observations",
    "procedures", "immunizations", "allergies", "careplans", "devices",
    "imaging_studies", "supplies", "organizations", "providers", "payers",
    "payer_transitions", "claims", "claims_transactions",
]


def main() -> None:
    if settings.db_engine != "duckdb":
        raise RuntimeError(
            f"load_bronze only supports DuckDB (got db_engine={settings.db_engine}). "
            f"For PostgreSQL, load bronze CSVs via COPY or an ETL tool."
        )

    csv_dir = settings.synthea_dir / "csv"
    if not csv_dir.exists():
        raise FileNotFoundError(
            f"Synthea CSVs not found in {csv_dir}. "
            f"Generate them with Synthea and unzip into data/synthea/."
        )

    db_path = settings.warehouse_db_abs
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = get_connection()
    con.execute("DROP SCHEMA IF EXISTS bronze CASCADE;")
    con.execute("CREATE SCHEMA bronze;")

    print(f"Loading Synthea Bronze into {db_path}")
    total = 0
    for name in SYNTHEA_TABLES:
        path = csv_dir / f"{name}.csv"
        if not path.exists():
            print(f"  - {name:<20} (skipped: file absent)")
            continue
        # all_varchar=true => keep raw text; Silver will cast/clean.
        con.execute(
            f"CREATE TABLE bronze.{name} AS "
            f"SELECT * FROM read_csv_auto('{path.as_posix()}', "
            f"header = true, all_varchar = true);"
        )
        n = con.execute(f"SELECT count(*) FROM bronze.{name};").fetchone()[0]
        total += n
        print(f"  - bronze.{name:<20} {n:>8} rows")

    con.close()
    print(f"Bronze layer ready ({total:,} rows total).")


if __name__ == "__main__":
    main()
