# Governance — RGPD / HDS by design

Health data engineering is as much about **governance** as about pipelines. This
project is built so the same safeguards would hold on real data.

## 1. No real data, ever

The dataset is **100% synthetic** (Synthea) — no patient, no re-identification
risk. Generated data is **git-ignored** and never committed, even though it is
synthetic (good reflex + keeps the repo light).

## 2. Minimisation & pseudonymisation

- The OMOP `person` table carries **no direct identifiers** (no name, SSN,
  address) — only a surrogate `person_id` and the source UUID as
  `person_source_value`. On real data, that UUID would be a **pseudonym**
  produced by a separate, access-controlled pseudonymisation service.
- Only the attributes needed for research (demographics, events, measurements)
  are modelled — **data minimisation**.

## 3. Least privilege & no free SQL on patient data

- The cohort layer (`cohort/builder.py`) is **read-only** and only exposes
  **parameterized** operations. User input is always **bound as a query
  parameter**, never string-interpolated → no injection surface.
- The AI agent can **only** call these governed operations — it **never writes
  SQL** and never sees raw patient rows. This is the health-appropriate form of
  agentic analytics.

## 4. Traceability

- Every agent action is logged as a step (which operation, which parameters,
  what result) — an audit trail of who asked what.
- dbt provides **lineage** from Synthea source → OMOP tables, and the FHIR export
  records the source vocabulary for every code.

## 5. Standards & interoperability

- **OMOP CDM** (research) and **FHIR** (exchange) are the recognised standards;
  using them is itself a governance choice (reproducibility, portability).
- Vocabulary mapping (`concept_id`) is isolated and documented
  ([`omop_mapping.md`](omop_mapping.md)) so it can be validated (Usagi-style,
  human-in-the-loop) rather than trusted blindly.

## 6. Sovereignty (HDS / SecNumCloud)

French health data must be hosted by an **HDS-certified** provider, and the most
sensitive public platforms are moving to **SecNumCloud** (sovereign, outside the
US Cloud Act) — e.g. the Plateforme des Données de Santé migrating off Azure.
This project is **cloud-agnostic** (Python, DuckDB/PostgreSQL, Docker) and its
deployment target is a **sovereign** cloud (OVH / Scaleway), aligning with that
requirement.

## 7. What would change on real data

- Real pseudonymisation service + key management.
- Access control (RBAC), audit logging to a SIEM, and a data-access committee.
- A declared legal basis (RGPD), reference methodology (CNIL **MR-004** for
  research), and DPO oversight.
- Hosting on an **HDS-certified / SecNumCloud** infrastructure.
