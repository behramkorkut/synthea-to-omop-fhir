SHELL := /bin/bash
ROOT  := $(shell pwd)

# Absolute paths so dbt works from any directory.
export WAREHOUSE_DB     ?= $(ROOT)/data/omop.duckdb
export DBT_PROFILES_DIR := $(ROOT)/dbt/omop_cdm

DBT  := uv run dbt
PROJ := --project-dir dbt/omop_cdm --profiles-dir dbt/omop_cdm

.PHONY: help setup synthea bronze omop quality fhir-export fhir-server fhir-push \
        api ask dashboard test format lint typecheck check clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install the environment (uv sync)
	uv sync

synthea: ## Generate synthetic patients with Synthea (needs Java)
	bash scripts/generate_synthea.sh

bronze: ## Load Synthea CSVs into DuckDB (bronze schema)
	uv run python -m synthea_omop_fhir.load_bronze

omop: ## Transform Synthea -> OMOP CDM with dbt (+ tests)
	$(DBT) build $(PROJ)

quality: ## Run health data-quality checks (Pandera / DQD-like)
	uv run python -m synthea_omop_fhir.quality.run

fhir-export: ## Export a subset of OMOP as FHIR resources
	uv run python -m synthea_omop_fhir.fhir.export

fhir-server: ## Start a HAPI FHIR server (Docker)
	docker compose -f docker/hapi-fhir.yml up -d

fhir-push: ## Load the FHIR bundle into the running HAPI server
	uv run python -m synthea_omop_fhir.fhir.push

api: ## Serve the cohort / FHIR facade API (FastAPI)
	uv run uvicorn synthea_omop_fhir.api.main:app --reload --port 8000

ask: ## Ask the governed clinical agent, e.g. make ask Q="patients with breast cancer?"
	uv run python -m synthea_omop_fhir.agent.cli "$(Q)"

dashboard: ## Launch the cohort explorer (Streamlit)
	uv run streamlit run app.py

test: ## Run the pytest suite
	uv run pytest

format: ## Auto-format + autofix (ruff)
	uv run ruff check --fix . && uv run ruff format .

lint: ## Lint + format check (read-only)
	uv run ruff check . && uv run ruff format --check .

typecheck: ## Static type-check (mypy)
	uv run mypy synthea_omop_fhir

check: lint test ## Quality gates: lint + tests

clean: ## Remove generated artifacts
	rm -rf data/synthea/csv data/fhir data/*.duckdb data/*.duckdb.wal \
		dbt/omop_cdm/target dbt/omop_cdm/logs
