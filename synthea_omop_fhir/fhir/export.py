"""Export a cohort from the OMOP CDM as FHIR R4 resources.

We read OMOP tables from DuckDB and build validated FHIR resources
(Patient, Encounter, Condition, Observation) with `fhir.resources`, then
assemble a FHIR **transaction Bundle** (POST with urn:uuid refs, so
references resolve on ingest). Load it into HAPI FHIR with `make fhir-push`.

Run:  uv run python -m synthea_omop_fhir.fhir.export [n_patients]
"""

from __future__ import annotations

import json
import sys
import uuid

import duckdb

# FHIR R4B (the version deployed in most EHRs / HAPI FHIR), not the library's R5 default.
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient

from ..config import settings

DEFAULT_N_PATIENTS = 25
MAX_OBSERVATIONS = 500  # keep the demo bundle small

GENDER = {8507: "male", 8532: "female"}
# OMOP visit concept -> HL7 v3 ActCode class
VISIT_CLASS = {9201: "IMP", 9203: "EMER"}
SNOMED = "http://snomed.info/sct"
LOINC = "http://loinc.org"


def _iso(d) -> str | None:
    return d.isoformat() if d is not None else None


def _validated(model_cls, payload: dict) -> dict:
    """Construct (=validate) a FHIR resource, return it as a plain dict."""
    return json.loads(model_cls(**payload).model_dump_json(exclude_none=True))


def build_bundle(con: duckdb.DuckDBPyConnection, n_patients: int) -> dict:
    con.execute("USE omop.omop")
    entries: list[dict] = []

    def add(resource: dict, resource_type: str) -> str:
        """Add a resource as a POST entry with a urn:uuid fullUrl; return the urn."""
        urn = f"urn:uuid:{uuid.uuid4()}"
        entries.append({
            "fullUrl": urn,
            "resource": resource,
            "request": {"method": "POST", "url": resource_type},
        })
        return urn

    # --- cohort: first N persons; keep person_id -> urn to link children --
    persons = con.execute(
        "SELECT person_id, gender_concept_id, year_of_birth, month_of_birth, "
        "day_of_birth, person_source_value FROM person ORDER BY person_id LIMIT ?",
        [n_patients],
    ).fetchall()
    ids = [r[0] for r in persons]

    patient_urn: dict[int, str] = {}
    for pid, gender, y, m, d, src in persons:
        patient_urn[pid] = add(_validated(Patient, {
            "identifier": [{"system": "urn:synthea", "value": src}],
            "gender": GENDER.get(gender, "unknown"),
            "birthDate": f"{int(y):04d}-{int(m):02d}-{int(d):02d}",
        }), "Patient")

    if not ids:
        return {"resourceType": "Bundle", "type": "transaction", "entry": entries}

    # --- encounters (reference the Patient by its urn:uuid) -------------
    for pid, start, end, vc in con.execute(
        "SELECT person_id, visit_start_date, visit_end_date, visit_concept_id "
        "FROM visit_occurrence WHERE person_id IN (SELECT UNNEST(?))",
        [ids],
    ).fetchall():
        add(_validated(Encounter, {
            "status": "finished",
            "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                      "code": VISIT_CLASS.get(vc, "AMB")},
            "subject": {"reference": patient_urn[pid]},
            "period": {"start": _iso(start), "end": _iso(end)},
        }), "Encounter")

    # --- conditions (SNOMED source code) --------------------------------
    for pid, code, onset in con.execute(
        "SELECT person_id, condition_source_value, condition_start_date "
        "FROM condition_occurrence WHERE person_id IN (SELECT UNNEST(?))",
        [ids],
    ).fetchall():
        add(_validated(Condition, {
            "clinicalStatus": {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                "code": "active"}]},
            "code": {"coding": [{"system": SNOMED, "code": code}]},
            "subject": {"reference": patient_urn[pid]},
            "onsetDateTime": _iso(onset),
        }), "Condition")

    # --- measurements -> Observation (LOINC source code) ----------------
    for pid, code, when, val, unit in con.execute(
        "SELECT person_id, measurement_source_value, measurement_date, "
        "value_as_number, unit_source_value FROM measurement "
        "WHERE person_id IN (SELECT UNNEST(?)) AND value_as_number IS NOT NULL LIMIT ?",
        [ids, MAX_OBSERVATIONS],
    ).fetchall():
        add(_validated(Observation, {
            "status": "final",
            "code": {"coding": [{"system": LOINC, "code": code}]},
            "subject": {"reference": patient_urn[pid]},
            "effectiveDateTime": _iso(when),
            "valueQuantity": {"value": float(val), "unit": unit or ""},
        }), "Observation")

    return {"resourceType": "Bundle", "type": "transaction", "entry": entries}


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_N_PATIENTS
    con = duckdb.connect(str(settings.warehouse_db_abs))
    bundle = build_bundle(con, n)
    con.close()

    settings.fhir_out_dir.mkdir(parents=True, exist_ok=True)
    out = settings.fhir_out_dir / "bundle.json"
    out.write_text(json.dumps(bundle, indent=2))

    counts: dict[str, int] = {}
    for e in bundle["entry"]:
        rt = e["resource"]["resourceType"]
        counts[rt] = counts.get(rt, 0) + 1
    print(f"FHIR transaction bundle written to {out}")
    print(f"  cohort: {n} patients")
    for rt, c in sorted(counts.items()):
        print(f"  {rt:<12} {c:>5}")
    print(f"  total resources: {len(bundle['entry'])}")


if __name__ == "__main__":
    main()
