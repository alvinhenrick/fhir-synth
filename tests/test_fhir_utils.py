"""Tests for FHIR utilities."""

from datetime import date

from fhir_synth.fhir_utils import FHIRResourceFactory


def test_create_patient():
    patient = FHIRResourceFactory.create_patient(
        id="p1",
        given_name="Jane",
        family_name="Doe",
        birth_date="1990-01-01",
    )

    assert patient.id == "p1"
    assert patient.name[0].family == "Doe"
    assert patient.birthDate == date(1990, 1, 1)


def test_create_condition():
    condition = FHIRResourceFactory.create_condition(
        id="c1",
        code="E11.9",
        patient_id="p1",
    )

    assert condition.id == "c1"
    assert condition.subject.reference == "Patient/p1"
