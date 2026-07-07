# synthea-to-omop-fhir

> A **governed, sovereign health-data pipeline**: synthetic patients → **OMOP CDM**
> (research) → **FHIR** (interoperability), with data-quality checks and a governed
> AI layer. Zero real data, zero RGPD.

![status](https://img.shields.io/badge/status-WIP-orange)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![OMOP](https://img.shields.io/badge/OMOP_CDM-OHDSI-005A9C)
![FHIR](https://img.shields.io/badge/FHIR-HL7_R4-E4002B)
![dbt](https://img.shields.io/badge/dbt-DuckDB-FF694B?logo=dbt&logoColor=white)

Portfolio project to demonstrate **health-data engineering** on the two standards
that matter in a French *Entrepôt de Données de Santé* (EDS): **OMOP CDM** (OHDSI,
for reproducible research) and **FHIR** (HL7, for interoperability) — built on
**Synthea** synthetic patients, with a **sovereign** deployment path.

## Why this project

The EDS world speaks two languages: **OMOP** (research/analytics) and **FHIR**
(exchange). This project speaks both, end to end, with the software rigor
(tests, CI, containers) and the **governance/sovereignty** awareness
(RGPD, HDS, SecNumCloud) that health-data teams require.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full diagram and the
rationale behind each choice. In short:

```
Synthea → Bronze (DuckDB) → dbt staging → OMOP CDM → { data quality, cohorts,
                                                       FHIR export → HAPI FHIR }
                                                     → governed AI + API/dashboard
```

## Standards, in one line each

- **OMOP CDM** (OHDSI): a common schema + standard vocabularies so any health
  dataset can be queried the same way → reproducible, multi-center research.
- **FHIR** (HL7): REST resources (`Patient`, `Encounter`, `Condition`,
  `Observation`…) → the interoperability lingua franca.
- **Synthea**: open-source synthetic patient generator → realistic but fake data.

## Quickstart (built in phases)

Requires [uv](https://docs.astral.sh/uv/) and Java 11+ (for Synthea).

```bash
make setup            # uv sync
make synthea          # generate synthetic patients (Java)
make bronze           # load Synthea CSVs into DuckDB
make omop             # Synthea -> OMOP CDM (dbt) + tests
make quality          # health data-quality checks
make fhir-export      # OMOP subset -> FHIR resources
make fhir-server      # HAPI FHIR server (Docker)
make api              # cohort / FHIR facade API
make dashboard        # cohort explorer (Streamlit)
```

Run `make help` to see every target.

## Roadmap

- [x] Scaffold (uv, structure, config, architecture)
- [ ] Synthea → Bronze (DuckDB)
- [ ] dbt: Synthea → OMOP CDM + data-quality checks
- [ ] OMOP → FHIR export + HAPI FHIR server
- [ ] Cohort builder + governed AI agent + API/dashboard
- [ ] Docker + sovereign deployment (OVH) + governance & tests

## Governance

Health data by design: **100% synthetic** data, documented pseudonymisation,
traceability and explicit purposes. See
[`docs/governance_rgpd_hds.md`](docs/governance_rgpd_hds.md).

## License

MIT.
