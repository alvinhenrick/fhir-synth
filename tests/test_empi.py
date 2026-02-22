"""Tests for EMPI-style Person/Patient generation."""

from fhir_synth.rule_engine import RuleEngine


def test_generate_empi_resources_links_person_to_patients():
    engine = RuleEngine()
    resources = engine.generate_empi_resources(persons=1, systems=["emr1", "emr2"])

    persons = [r for r in resources if r.get("resourceType") == "Person"]
    patients = [r for r in resources if r.get("resourceType") == "Patient"]
    orgs = [r for r in resources if r.get("resourceType") == "Organization"]

    assert len(persons) == 1
    assert len(patients) == 2
    assert len(orgs) == 2
    assert len(persons[0]["link"]) == 2

    patient_refs = {link["target"]["reference"] for link in persons[0]["link"]}
    assert patient_refs == {"Patient/emr1-patient-1", "Patient/emr2-patient-1"}
