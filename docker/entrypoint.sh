#!/usr/bin/env bash
# Build the OMOP warehouse on first boot (if Synthea CSVs are mounted), then serve.
# Arg selects the interface: "api" (default) or "dashboard".
set -euo pipefail
cd /app

if [ ! -f "$WAREHOUSE_DB" ]; then
  if [ -d data/synthea/csv ]; then
    echo "[init] Warehouse not found — building OMOP CDM from Synthea CSVs…"
    uv run python -m synthea_omop_fhir.load_bronze
    ( export DBT_PROFILES_DIR="$PWD/dbt/omop_cdm"; \
      uv run dbt build --project-dir dbt/omop_cdm --profiles-dir dbt/omop_cdm )
  else
    echo "[warn] No warehouse and no data/synthea/csv mounted — generate Synthea first."
  fi
fi

MODE="${1:-api}"
if [ "$MODE" = "dashboard" ]; then
  echo "[run] Streamlit cohort explorer on http://localhost:8501"
  exec uv run streamlit run app.py \
    --server.port 8501 --server.address 0.0.0.0 --server.headless true
fi

echo "[run] Cohort API on http://localhost:8000/docs"
exec uv run uvicorn synthea_omop_fhir.api.main:app --host 0.0.0.0 --port 8000
