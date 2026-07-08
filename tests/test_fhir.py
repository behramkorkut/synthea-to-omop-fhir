"""FHIR export — pure unit tests (no warehouse needed)."""

from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient

from synthea_omop_fhir.fhir.export import _validated


def test_validated_patient_is_r4b_dict():
    d = _validated(Patient, {"gender": "female", "birthDate": "1980-01-01"})
    assert d["resourceType"] == "Patient"
    assert d["gender"] == "female"


def test_validated_observation_value_quantity():
    d = _validated(Observation, {
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
        "subject": {"reference": "urn:uuid:abc"},
        "valueQuantity": {"value": 72, "unit": "/min"},
    })
    assert d["valueQuantity"]["value"] == 72
