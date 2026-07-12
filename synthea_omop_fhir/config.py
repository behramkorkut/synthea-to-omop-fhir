"""Typed configuration (pydantic-settings).

All runtime config comes from the environment / .env — never hard-coded.
Paths are resolved as absolutes so tools (dbt, FHIR export) work from any dir.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# synthea_omop_fhir/ -> project root is its parent
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Warehouse / dbt -------------------------------------------------
    # OMOP CDM lives in DuckDB for a zero-cost, reproducible demo.
    # Prod target = PostgreSQL (documented) — the usual EDS backend.
    warehouse_db: Path = PROJECT_ROOT / "data" / "omop.duckdb"
    dbt_project_dir: Path = PROJECT_ROOT / "dbt" / "omop_cdm"

    # --- Data locations --------------------------------------------------
    synthea_dir: Path = PROJECT_ROOT / "data" / "synthea"   # raw Synthea CSVs
    fhir_out_dir: Path = PROJECT_ROOT / "data" / "fhir"     # exported FHIR bundles

    # --- FHIR server (HAPI FHIR, run via Docker) -------------------------
    fhir_base_url: str = "http://localhost:8080/fhir"

    # --- API security ----------------------------------------------------
    api_key: str = ""                         # empty = no auth (demo mode)
    rate_limit_per_minute: int = 0             # 0 = disabled

    # --- LLM (governed clinical agent) ------------------------------------
    llm_provider: str = "anthropic"            # anthropic | openai
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    llm_base_url: str = ""                     # for local / proxy endpoints

    # --- Observability -----------------------------------------------------
    log_level: str = "INFO"                    # DEBUG | INFO | WARNING | ERROR
    log_format: str = "text"                   # text | json

    @property
    def warehouse_db_abs(self) -> Path:
        return (
            self.warehouse_db
            if self.warehouse_db.is_absolute()
            else (PROJECT_ROOT / self.warehouse_db).resolve()
        )


settings = Settings()
