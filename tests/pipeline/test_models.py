"""Tests for pipeline domain models — written first (TDD)."""

import pytest
from pydantic import ValidationError

from fhir_synth.pipeline.models import (
    ClinicalFinding,
    ClinicalPlan,
    Coding,
    MedicationEntry,
    PatientProfile,
)

# ── Coding ───────────────────────────────────────────────────────────────────


def test_coding_requires_system_and_code():
    c = Coding(system="http://snomed.info/sct", code="44054006")
    assert c.display == ""


def test_coding_display_optional():
    c = Coding(system="http://loinc.org", code="8867-4", display="Heart rate")
    assert c.display == "Heart rate"


def test_coding_rejects_empty_system():
    with pytest.raises(ValidationError):
        Coding(system="", code="44054006")


def test_coding_rejects_empty_code():
    with pytest.raises(ValidationError):
        Coding(system="http://snomed.info/sct", code="")


# ── ClinicalFinding ──────────────────────────────────────────────────────────


def test_clinical_finding_minimal():
    f = ClinicalFinding(
        coding=Coding(system="http://snomed.info/sct", code="44054006", display="Type 2 diabetes")
    )
    assert f.onset_description is None
    assert f.severity is None


def test_clinical_finding_full():
    f = ClinicalFinding(
        coding=Coding(system="http://snomed.info/sct", code="44054006"),
        onset_description="5 years ago",
        severity="moderate",
    )
    assert f.onset_description == "5 years ago"


# ── MedicationEntry ──────────────────────────────────────────────────────────


def test_medication_entry_minimal():
    m = MedicationEntry(rxnorm_code="6809", display="Metformin 500mg")
    assert m.dose is None
    assert m.frequency is None


def test_medication_entry_full():
    m = MedicationEntry(
        rxnorm_code="6809",
        display="Metformin 500mg",
        dose="500mg",
        frequency="twice daily",
    )
    assert m.dose == "500mg"


# ── PatientProfile ───────────────────────────────────────────────────────────


def test_patient_profile_minimal():
    p = PatientProfile(age=45, gender="female")
    assert p.conditions == []
    assert p.medications == []
    assert p.allergies == []
    assert p.race is None


def test_patient_profile_with_clinical_data():
    p = PatientProfile(
        age=67,
        gender="male",
        race="White",
        conditions=[
            ClinicalFinding(
                coding=Coding(system="http://snomed.info/sct", code="44054006", display="T2DM")
            )
        ],
        medications=[MedicationEntry(rxnorm_code="6809", display="Metformin")],
        allergies=["penicillin"],
    )
    assert len(p.conditions) == 1
    assert len(p.medications) == 1
    assert "penicillin" in p.allergies


def test_patient_profile_age_lower_bound():
    p = PatientProfile(age=0, gender="unknown")
    assert p.age == 0


def test_patient_profile_age_upper_bound():
    p = PatientProfile(age=120, gender="unknown")
    assert p.age == 120


def test_patient_profile_rejects_negative_age():
    with pytest.raises(ValidationError):
        PatientProfile(age=-1, gender="male")


def test_patient_profile_rejects_age_over_120():
    with pytest.raises(ValidationError):
        PatientProfile(age=121, gender="male")


def test_patient_profile_rejects_invalid_gender():
    with pytest.raises(ValidationError):
        PatientProfile(age=30, gender="robot")


# ── ClinicalPlan ─────────────────────────────────────────────────────────────


def test_clinical_plan_minimal():
    plan = ClinicalPlan(
        patients=[PatientProfile(age=40, gender="female")],
        care_setting="outpatient",
        encounter_type="routine visit",
    )
    assert plan.fhir_version == "R4B"
    assert plan.notes == ""


def test_clinical_plan_rejects_empty_patients():
    with pytest.raises(ValidationError):
        ClinicalPlan(patients=[], care_setting="outpatient", encounter_type="follow-up")


def test_clinical_plan_serialises_to_json():
    plan = ClinicalPlan(
        patients=[
            PatientProfile(
                age=55,
                gender="male",
                conditions=[
                    ClinicalFinding(
                        coding=Coding(
                            system="http://snomed.info/sct",
                            code="44054006",
                            display="Type 2 diabetes",
                        )
                    )
                ],
            )
        ],
        care_setting="outpatient clinic",
        encounter_type="follow-up",
        notes="Include HbA1c observations",
    )
    json_str = plan.model_dump_json()
    restored = ClinicalPlan.model_validate_json(json_str)
    assert restored.patients[0].age == 55
    assert restored.patients[0].conditions[0].coding.code == "44054006"


def test_clinical_plan_multiple_patients():
    plan = ClinicalPlan(
        patients=[
            PatientProfile(age=30, gender="female"),
            PatientProfile(age=60, gender="male"),
        ],
        care_setting="inpatient",
        encounter_type="admission",
    )
    assert len(plan.patients) == 2


def test_clinical_plan_fhir_version_preserved():
    plan = ClinicalPlan(
        patients=[PatientProfile(age=40, gender="other")],
        care_setting="community",
        encounter_type="home visit",
        fhir_version="STU3",
    )
    assert plan.fhir_version == "STU3"