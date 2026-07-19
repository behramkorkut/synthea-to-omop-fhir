"""Tests de l'ingestion Bronze (load_bronze.py) sur mini-CSV synthétiques.

Bronze = ingestion brute : toutes les colonnes en VARCHAR, sans nettoyage.
Les tests utilisent un warehouse DuckDB TEMPORAIRE (tmp_path) — le vrai
data/omop.duckdb n'est jamais touché.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from synthea_omop_fhir.config import settings
from synthea_omop_fhir.load_bronze import main


def _write_csv(csv_dir: Path, name: str, header: str, rows: list[str]) -> None:
    (csv_dir / f"{name}.csv").write_text(header + "\n" + "\n".join(rows) + "\n")


def test_main_loads_available_csvs_as_varchar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    csv_dir = tmp_path / "csv"
    csv_dir.mkdir()
    _write_csv(csv_dir, "patients", "Id,birthDate", ["p1,2020-01-01", "p2,2021-06-30"])
    _write_csv(csv_dir, "conditions", "START,STOP,CODE", ["2020-01-01,,E11"])
    db_file = tmp_path / "wh.duckdb"
    monkeypatch.setattr(settings, "synthea_dir", tmp_path)
    monkeypatch.setattr(settings, "warehouse_db", db_file)

    main()

    con = duckdb.connect(str(db_file))
    try:
        assert con.execute("SELECT count(*) FROM bronze.patients").fetchone()[0] == 2
        assert con.execute("SELECT count(*) FROM bronze.conditions").fetchone()[0] == 1
        # all_varchar : birthDate reste du TEXTE brut — typer/nettoyer est le
        # travail de la couche Silver (dbt), pas de Bronze.
        col_type = con.execute(
            "SELECT typeof(birthDate) FROM bronze.patients LIMIT 1"
        ).fetchone()[0]
        assert col_type == "VARCHAR"
        # Les tables sans CSV sont ignorées proprement (non créées).
        tables = {
            r[0]
            for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'bronze'"
            ).fetchall()
        }
        assert tables == {"patients", "conditions"}
    finally:
        con.close()


def test_main_missing_csv_dir_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # tmp_path ne contient PAS de sous-dossier csv/.
    monkeypatch.setattr(settings, "synthea_dir", tmp_path)
    with pytest.raises(FileNotFoundError, match="Synthea"):
        main()


def test_main_rejects_non_duckdb_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "db_engine", "postgres")
    with pytest.raises(RuntimeError, match="only supports DuckDB"):
        main()
