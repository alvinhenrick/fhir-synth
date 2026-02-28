"""Tests for FHIR spec auto-discovery."""

from fhir_synth.fhir_spec import (
    CLINICAL_RESOURCES,
    class_to_module,
    get_resource_class,
    import_guide,
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


def test_clinical_resources_includes_key_types():
    """Dynamic discovery should find the most important clinical resource types."""
    # These all have subject/patient/encounter/beneficiary fields
    expected = {
        "Patient",  # foundational
        "Practitioner",  # foundational
        "Organization",  # foundational
        "Condition",
        "Observation",
        "Procedure",
        "Encounter",
        "MedicationRequest",
        "DiagnosticReport",
        "Immunization",
        "AllergyIntolerance",
        "CarePlan",
        "Claim",
        "ExplanationOfBenefit",
    }
    clinical_set = set(CLINICAL_RESOURCES)
    for rt in expected:
        assert rt in clinical_set, f"{rt} not in dynamically discovered CLINICAL_RESOURCES"


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


# ── class_to_module introspection tests ───────────────────────────────────


def test_class_to_module_covers_data_types():
    """Data-type classes like TimingRepeat, CodeableConcept, HumanName should be mapped."""
    assert class_to_module("TimingRepeat") == "timing"
    assert class_to_module("Timing") == "timing"
    assert class_to_module("CodeableConcept") == "codeableconcept"
    assert class_to_module("HumanName") == "humanname"
    assert class_to_module("Coding") == "coding"
    assert class_to_module("Quantity") == "quantity"
    assert class_to_module("Reference") == "reference"


def test_class_to_module_covers_resources():
    """Resource classes should also be in the map."""
    assert class_to_module("Patient") == "patient"
    assert class_to_module("Observation") == "observation"
    assert class_to_module("Condition") == "condition"


def test_class_to_module_returns_none_for_unknown():
    """Unknown class names should return None."""
    assert class_to_module("NotARealClass") is None
    assert class_to_module("") is None


def test_class_to_module_dosage_subtypes():
    """DosageDoseAndRate should be in 'dosage', not 'dosagedoseandrate'."""
    assert class_to_module("Dosage") == "dosage"
    assert class_to_module("DosageDoseAndRate") == "dosage"


# ── import_guide tests ────────────────────────────────────────────────────


def test_import_guide_includes_requested_resources():
    """Import guide should contain exact import lines for requested resource types."""
    guide = import_guide(["Patient", "Condition"])
    assert "from fhir.resources.R4B.patient import Patient" in guide
    assert "from fhir.resources.R4B.condition import Condition" in guide


def test_import_guide_includes_common_data_types():
    """Import guide should always include common data-type modules."""
    guide = import_guide(["Patient"])
    assert "from fhir.resources.R4B.timing import" in guide
    assert "TimingRepeat" in guide
    assert "from fhir.resources.R4B.codeableconcept import" in guide
    assert "from fhir.resources.R4B.coding import" in guide


def test_import_guide_includes_warning():
    """Import guide should contain the warning about not inventing module names."""
    guide = import_guide(["Patient"])
    assert "Do NOT invent module names" in guide
    assert "timingrepeat" in guide
