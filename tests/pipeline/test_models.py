"""Tests for pipeline domain models — written first (TDD)."""

import pytest
from pydantic import ValidationError

from fhir_synth.pipeline.models import (
    ClinicalFinding,
    ClinicalPlan,
    Coding,
    EncounterEvent,
    LabValue,
    MedicationAction,
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


# ── LabValue ──────────────────────────────────────────────────────────────────


def test_lab_value_minimal():
    lab = LabValue(loinc_code="4548-4", display="HbA1c", value=9.2, unit="%")
    assert lab.interpretation is None


def test_lab_value_with_interpretation():
    lab = LabValue(loinc_code="4548-4", display="HbA1c", value=9.2, unit="%", interpretation="H")
    assert lab.interpretation == "H"


def test_lab_value_is_frozen():
    lab = LabValue(loinc_code="4548-4", display="HbA1c", value=9.2, unit="%")
    with pytest.raises((AttributeError, TypeError, ValidationError)):
        lab.value = 7.0  # type: ignore[misc]


# ── MedicationAction ──────────────────────────────────────────────────────────


def test_medication_action_start():
    action = MedicationAction(action="start", rxnorm_code="6809", display="Metformin 500mg")
    assert action.action == "start"
    assert action.dose is None
    assert action.reason is None


def test_medication_action_change_with_reason():
    action = MedicationAction(
        action="change",
        rxnorm_code="6809",
        display="Metformin 1000mg",
        dose="1000mg twice daily",
        reason="HbA1c above target",
    )
    assert action.dose == "1000mg twice daily"


def test_medication_action_stop():
    action = MedicationAction(
        action="stop", rxnorm_code="6809", display="Metformin 500mg", reason="GI intolerance"
    )
    assert action.action == "stop"


def test_medication_action_rejects_invalid_action():
    with pytest.raises(ValidationError):
        MedicationAction(action="pause", rxnorm_code="6809", display="Metformin")  # type: ignore[arg-type]


# ── EncounterEvent ────────────────────────────────────────────────────────────


def _hba1c(value: float) -> LabValue:
    return LabValue(loinc_code="4548-4", display="HbA1c", value=value, unit="%")


def test_encounter_event_minimal():
    event = EncounterEvent(month_offset=0, reason_display="Initial diagnosis")
    assert event.encounter_class == "AMB"
    assert event.labs == []
    assert event.vitals == []
    assert event.procedures == []
    assert event.new_conditions == []
    assert event.medication_changes == []


def test_encounter_event_with_labs_and_meds():
    event = EncounterEvent(
        month_offset=3,
        reason_display="Diabetic follow-up",
        labs=[_hba1c(8.1)],
        medication_changes=[
            MedicationAction(action="change", rxnorm_code="6809", display="Metformin 1000mg")
        ],
    )
    assert event.labs[0].value == 8.1
    assert event.medication_changes[0].action == "change"


def test_encounter_event_emergency_class():
    event = EncounterEvent(month_offset=7, encounter_class="EMER", reason_display="Chest pain")
    assert event.encounter_class == "EMER"


def test_encounter_event_rejects_invalid_class():
    with pytest.raises(ValidationError):
        EncounterEvent(month_offset=0, encounter_class="INVALID", reason_display="Visit")  # type: ignore[arg-type]


def test_encounter_event_rejects_negative_offset():
    with pytest.raises(ValidationError):
        EncounterEvent(month_offset=-1, reason_display="Visit")


def test_encounter_event_is_frozen():
    event = EncounterEvent(month_offset=0, reason_display="Visit")
    with pytest.raises((AttributeError, TypeError, ValidationError)):
        event.month_offset = 5  # type: ignore[misc]


# ── PatientProfile longitudinal fields ───────────────────────────────────────


def test_patient_profile_timeline_defaults_empty():
    p = PatientProfile(age=50, gender="male")
    assert p.timeline == []
    assert p.care_start_date is None


def test_patient_profile_with_timeline():
    p = PatientProfile(
        age=55,
        gender="female",
        care_start_date="2022-01-15",
        timeline=[
            EncounterEvent(month_offset=0, reason_display="T2DM diagnosis", labs=[_hba1c(9.2)]),
            EncounterEvent(month_offset=3, reason_display="Follow-up", labs=[_hba1c(8.1)]),
            EncounterEvent(month_offset=6, reason_display="Follow-up", labs=[_hba1c(7.4)]),
        ],
    )
    assert len(p.timeline) == 3
    assert p.timeline[0].labs[0].value == 9.2
    assert p.timeline[2].labs[0].value == 7.4


def test_patient_profile_timeline_serialises():
    p = PatientProfile(
        age=55,
        gender="female",
        care_start_date="2022-01-15",
        timeline=[EncounterEvent(month_offset=0, reason_display="Visit", labs=[_hba1c(9.0)])],
    )
    restored = PatientProfile.model_validate_json(p.model_dump_json())
    assert restored.timeline[0].labs[0].loinc_code == "4548-4"
    assert restored.care_start_date == "2022-01-15"


# ── ClinicalPlan longitudinal fields ─────────────────────────────────────────


def test_clinical_plan_time_span_default_zero():
    plan = ClinicalPlan(
        patients=[PatientProfile(age=40, gender="female")],
        care_setting="outpatient",
        encounter_type="follow-up",
    )
    assert plan.time_span_months == 0


def test_clinical_plan_time_span_set():
    plan = ClinicalPlan(
        patients=[PatientProfile(age=40, gender="female")],
        care_setting="outpatient",
        encounter_type="follow-up",
        time_span_months=24,
    )
    assert plan.time_span_months == 24


def test_clinical_plan_rejects_negative_time_span():
    with pytest.raises(ValidationError):
        ClinicalPlan(
            patients=[PatientProfile(age=40, gender="female")],
            care_setting="outpatient",
            encounter_type="follow-up",
            time_span_months=-1,
        )


def test_clinical_plan_longitudinal_round_trip():
    """Full longitudinal plan survives JSON serialisation."""
    plan = ClinicalPlan(
        patients=[
            PatientProfile(
                age=55,
                gender="female",
                care_start_date="2022-01-15",
                timeline=[
                    EncounterEvent(
                        month_offset=0,
                        reason_display="Diabetes diagnosis",
                        labs=[_hba1c(9.2)],
                        medication_changes=[
                            MedicationAction(
                                action="start", rxnorm_code="6809", display="Metformin 500mg"
                            )
                        ],
                    ),
                    EncounterEvent(month_offset=3, reason_display="Follow-up", labs=[_hba1c(8.1)]),
                ],
            )
        ],
        care_setting="outpatient clinic",
        encounter_type="follow-up",
        time_span_months=12,
    )
    restored = ClinicalPlan.model_validate_json(plan.model_dump_json(indent=2))
    assert restored.time_span_months == 12
    assert len(restored.patients[0].timeline) == 2
    assert restored.patients[0].timeline[0].medication_changes[0].rxnorm_code == "6809"
