"""Tests for PlanEnricher (Stage 1.5) — TDD.

PlanEnricher walks the FHIR dependency graph to detect missing resource
companions in a ClinicalPlan and adds minimal stubs so Stage 2 can
generate valid, reference-complete FHIR resources.
"""

from __future__ import annotations

import pytest

from fhir_synth.pipeline.models import (
    CareTeamMember,
    ClinicalFinding,
    ClinicalPlan,
    Coding,
    MedicationEntry,
    PatientProfile,
)
from fhir_synth.pipeline.plan_enricher import PlanEnricher


# ── Helpers ───────────────────────────────────────────────────────────────────


def _patient_with_medications() -> PatientProfile:
    return PatientProfile(
        age=50,
        gender="female",
        medications=[
            MedicationEntry(rxnorm_code="6809", display="Metformin 500mg"),
        ],
    )


def _patient_with_conditions_only() -> PatientProfile:
    return PatientProfile(
        age=40,
        gender="male",
        conditions=[
            ClinicalFinding(
                coding=Coding(
                    system="http://snomed.info/sct",
                    code="44054006",
                    display="Type 2 diabetes mellitus",
                )
            )
        ],
    )


def _bare_plan(patients: list[PatientProfile] | None = None) -> ClinicalPlan:
    return ClinicalPlan(
        patients=patients or [_patient_with_medications()],
        care_setting="outpatient clinic",
        encounter_type="follow-up",
    )


# ── Core enrichment logic ─────────────────────────────────────────────────────


def test_enricher_adds_practitioner_when_medications_present() -> None:
    """Plan with MedicationRequest needs a Practitioner for requester (US Core)."""
    plan = _bare_plan()
    enriched = PlanEnricher().enrich(plan)

    roles = {m.role for m in enriched.care_team}
    assert "Practitioner" in roles, "Practitioner should be added for MedicationRequest.requester"


def test_enricher_no_changes_when_no_medications_and_no_conditions() -> None:
    """A plan with only demographics needs no companions."""
    plan = _bare_plan(
        patients=[PatientProfile(age=30, gender="male")]
    )
    enriched = PlanEnricher().enrich(plan)
    assert enriched.care_team == []


def test_enricher_no_changes_when_conditions_only() -> None:
    """Condition.subject → Patient (always present); no extra companion needed."""
    plan = _bare_plan(patients=[_patient_with_conditions_only()])
    enriched = PlanEnricher().enrich(plan)
    assert enriched.care_team == []


def test_enricher_does_not_duplicate_existing_practitioner() -> None:
    """If plan already has a Practitioner, no second entry is added."""
    existing = CareTeamMember(role="Practitioner", display_name="Dr. Jones")
    plan = ClinicalPlan(
        patients=[_patient_with_medications()],
        care_setting="outpatient clinic",
        encounter_type="follow-up",
        care_team=[existing],
    )
    enriched = PlanEnricher().enrich(plan)

    practitioners = [m for m in enriched.care_team if m.role == "Practitioner"]
    assert len(practitioners) == 1, "Must not add duplicate Practitioner"
    assert practitioners[0].display_name == "Dr. Jones"  # preserved original


def test_enricher_preserves_plan_immutability() -> None:
    """Enrich must return a new plan, not mutate the original."""
    plan = _bare_plan()
    enriched = PlanEnricher().enrich(plan)

    assert enriched is not plan
    assert plan.care_team == []  # original untouched


def test_enricher_preserves_all_existing_plan_fields() -> None:
    """Enrichment must not alter any existing plan field."""
    plan = _bare_plan()
    enriched = PlanEnricher().enrich(plan)

    assert enriched.patients == plan.patients
    assert enriched.care_setting == plan.care_setting
    assert enriched.encounter_type == plan.encounter_type
    assert enriched.notes == plan.notes
    assert enriched.fhir_version == plan.fhir_version


def test_enricher_multiple_patients_one_practitioner() -> None:
    """Multiple patients with medications should still produce exactly one Practitioner."""
    plan = ClinicalPlan(
        patients=[_patient_with_medications(), _patient_with_medications()],
        care_setting="clinic",
        encounter_type="follow-up",
    )
    enriched = PlanEnricher().enrich(plan)

    practitioners = [m for m in enriched.care_team if m.role == "Practitioner"]
    assert len(practitioners) == 1


def test_enricher_noop_when_plan_already_enriched() -> None:
    """Calling enrich twice must be idempotent."""
    plan = _bare_plan()
    once = PlanEnricher().enrich(plan)
    twice = PlanEnricher().enrich(once)

    practitioners = [m for m in twice.care_team if m.role == "Practitioner"]
    assert len(practitioners) == 1


# ── Default display names ─────────────────────────────────────────────────────


def test_enricher_practitioner_has_sensible_default_name() -> None:
    """Auto-added Practitioner must have a non-empty display name."""
    plan = _bare_plan()
    enriched = PlanEnricher().enrich(plan)

    practitioner = next(m for m in enriched.care_team if m.role == "Practitioner")
    assert practitioner.display_name  # non-empty


# ── FHIR spec integration ─────────────────────────────────────────────────────


def test_enricher_uses_fhir_spec_for_allowed_types() -> None:
    """reference_allowed_types must confirm Practitioner is valid for MedicationRequest.requester."""
    from fhir_synth.fhir_spec import reference_allowed_types

    allowed = reference_allowed_types("MedicationRequest")
    assert "requester" in allowed
    assert "Practitioner" in allowed["requester"]


def test_reference_allowed_types_returns_typed_list() -> None:
    """Smoke test: reference_allowed_types returns populated dict for common resources."""
    from fhir_synth.fhir_spec import reference_allowed_types

    for res in ("MedicationRequest", "Observation", "Condition", "Encounter"):
        result = reference_allowed_types(res)
        assert isinstance(result, dict)
        for k, v in result.items():
            assert isinstance(k, str)
            assert isinstance(v, list)
            assert all(isinstance(t, str) for t in v)
