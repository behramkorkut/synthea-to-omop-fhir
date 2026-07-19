"""FHIR export — pure unit tests (no warehouse needed)."""

from datetime import date, datetime

from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient

from synthea_omop_fhir.fhir.export import _iso, _validated, build_bundle


def test_validated_patient_is_r4b_dict():
    d = _validated(Patient, {"gender": "female", "birthDate": "1980-01-01"})
    assert d["resourceType"] == "Patient"
    assert d["gender"] == "female"


def test_validated_observation_value_quantity():
    d = _validated(
        Observation,
        {
            "status": "final",
            "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
            "subject": {"reference": "urn:uuid:abc"},
            "valueQuantity": {"value": 72, "unit": "/min"},
        },
    )
    assert d["valueQuantity"]["value"] == 72


# --- _iso helper ---


def test_iso_with_date():
    assert _iso(date(1980, 1, 15)) == "1980-01-15"


def test_iso_with_datetime():
    assert _iso(datetime(2020, 6, 1, 12, 30, 0)) == "2020-06-01T12:30:00"


def test_iso_with_none():
    assert _iso(None) is None


# --- build_bundle with mock connection ---


class FakeConnection:
    def __init__(self, persons=None, visits=None, conditions=None, measurements=None):
        self._persons = persons or []
        self._visits = visits or []
        self._conditions = conditions or []
        self._measurements = measurements or []
        self._last_result = []
        self._current_sql = ""

    def execute(self, sql, params=None):
        self._current_sql = sql
        return self

    def fetchall(self):
        if "FROM person" in self._current_sql:
            return self._persons
        elif "FROM visit_occurrence" in self._current_sql:
            return self._visits
        elif "FROM condition_occurrence" in self._current_sql:
            return self._conditions
        elif "FROM measurement" in self._current_sql:
            return self._measurements
        return []

    def fetchone(self):
        return None


def test_build_bundle_empty_cohort():
    """Empty cohort returns empty bundle."""
    con = FakeConnection()
    bundle = build_bundle(con, 0)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "transaction"
    assert len(bundle["entry"]) == 0


def test_build_bundle_with_one_patient():
    con = FakeConnection(
        persons=[(1, 8507, 1980, 1, 15, "p1")],
        visits=[],
        conditions=[],
        measurements=[],
    )
    bundle = build_bundle(con, 1)
    assert len(bundle["entry"]) == 1
    assert bundle["entry"][0]["resource"]["resourceType"] == "Patient"
    assert bundle["entry"][0]["resource"]["gender"] == "male"
    assert bundle["entry"][0]["resource"]["birthDate"] == "1980-01-15"


def test_build_bundle_patient_count_matches_cohort():
    con = FakeConnection(
        persons=[(1, 8507, 1980, 1, 15, "p1"), (2, 8532, 1990, 6, 20, "p2")],
        visits=[],
        conditions=[],
        measurements=[],
    )
    bundle = build_bundle(con, 2)
    patients = [
        e for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient"
    ]
    assert len(patients) == 2


def test_build_bundle_links_encounter_to_patient():
    con = FakeConnection(
        persons=[(1, 8507, 1980, 1, 15, "p1")],
        visits=[(1, date(2020, 1, 1), date(2020, 1, 5), 9201)],
        conditions=[],
        measurements=[],
    )
    bundle = build_bundle(con, 1)
    encounters = [
        e for e in bundle["entry"] if e["resource"]["resourceType"] == "Encounter"
    ]
    assert len(encounters) == 1
    assert encounters[0]["resource"]["status"] == "finished"
    # The encounter references the patient via the generated urn:uuid
    assert "urn:uuid:" in encounters[0]["resource"]["subject"]["reference"]


def test_build_bundle_with_condition():
    con = FakeConnection(
        persons=[(1, 8507, 1980, 1, 15, "p1")],
        visits=[],
        conditions=[(1, "C001", date(2020, 3, 1))],
        measurements=[],
    )
    bundle = build_bundle(con, 1)
    conditions = [
        e for e in bundle["entry"] if e["resource"]["resourceType"] == "Condition"
    ]
    assert len(conditions) == 1
    assert conditions[0]["resource"]["code"]["coding"][0]["code"] == "C001"


def test_build_bundle_with_observation():
    con = FakeConnection(
        persons=[(1, 8507, 1980, 1, 15, "p1")],
        visits=[],
        conditions=[],
        measurements=[(1, "8867-4", date(2020, 4, 1), 72.0, "/min")],
    )
    bundle = build_bundle(con, 1)
    obs = [e for e in bundle["entry"] if e["resource"]["resourceType"] == "Observation"]
    assert len(obs) == 1
    assert obs[0]["resource"]["valueQuantity"]["value"] == 72.0
    assert obs[0]["resource"]["valueQuantity"]["unit"] == "/min"


def test_max_observations_constant():
    """MAX_OBSERVATIONS should be 500 to keep bundles small."""
    from synthea_omop_fhir.fhir.export import MAX_OBSERVATIONS

    assert MAX_OBSERVATIONS == 500


def test_build_bundle_urn_refs_resolve():
    """All Patient references should be valid urn:uuid strings."""
    con = FakeConnection(
        persons=[(1, 8507, 1980, 1, 15, "p1")],
        visits=[(1, date(2020, 1, 1), date(2020, 1, 5), 9201)],
        conditions=[(1, "C001", date(2020, 3, 1))],
        measurements=[(1, "8867-4", date(2020, 4, 1), 72.0, "/min")],
    )
    bundle = build_bundle(con, 1)
    # Every entry should have a fullUrl and a POST request
    for entry in bundle["entry"]:
        assert entry["fullUrl"].startswith("urn:uuid:")
        assert entry["request"]["method"] == "POST"
        assert "resourceType" in entry["resource"]
