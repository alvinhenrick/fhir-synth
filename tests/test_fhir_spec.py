"""Tests for FHIR spec auto-discovery."""

from fhir_synth.fhir_spec import (
    CLINICAL_RESOURCES,
    get_resource_class,
    required_fields,
    resource_names,
    spec_summary,
)


def test_resource_names_discovers_many_types():
    """fhir.resources R4B has ~141 resource modules — we should find them."""
    names = resource_names()
    assert len(names) > 100, f"Expected 100+ resources, got {len(names)}"
    # Spot-check common types
    for expected in ["Patient", "Condition", "Observation", "Bundle", "Encounter"]:
        assert expected in names, f"{expected} not found"


def test_get_resource_class_returns_pydantic_model():
    """get_resource_class should return a class with model_fields."""
    cls = get_resource_class("Patient")
    assert hasattr(cls, "model_fields")
    assert "id" in cls.model_fields


def test_get_resource_class_unknown_raises():
    """Unknown resource type should raise ValueError."""
    import pytest

    with pytest.raises(ValueError, match="Unknown FHIR resource type"):
        get_resource_class("NotARealResource")


def test_required_fields_condition():
    """Condition requires 'subject'."""
    req = required_fields("Condition")
    assert "subject" in req


def test_required_fields_observation():
    """Observation requires 'code'."""
    req = required_fields("Observation")
    assert "code" in req


def test_clinical_resources_is_subset_of_all():
    """CLINICAL_RESOURCES should be a subset of resource_names()."""
    all_names = set(resource_names())
    for rt in CLINICAL_RESOURCES:
        assert rt in all_names, f"{rt} not in all resource names"


def test_spec_summary_returns_text():
    """spec_summary should return a non-empty string."""
    summary = spec_summary(["Patient", "Condition"])
    assert "Patient" in summary
    assert "Condition" in summary
    assert "required:" in summary


def test_no_concatenation_bugs_in_resource_names():
    """Each resource name should be short and start with uppercase."""
    for name in resource_names():
        assert name[0].isupper(), f"{name} does not start with uppercase"
        assert len(name) < 40, f"{name} looks like a concatenation bug"

