"""Tests for FHIR resource validation."""

from fhir_synth.code_generator.fhir_validation import (
    ValidationResult,
    _check_choice_type_fields,
    validate_resource,
    validate_resources,
)


def test_validate_resource_valid_patient():
    resource = {"resourceType": "Patient", "id": "p1", "gender": "male"}
    errors = validate_resource(resource)
    assert errors == []


def test_validate_resource_missing_resource_type():
    errors = validate_resource({"id": "p1"})
    assert len(errors) == 1
    assert "resourceType" in errors[0]


def test_validate_resource_unknown_resource_type():
    errors = validate_resource({"resourceType": "FakeResource"})
    assert len(errors) == 1
    assert "Unknown" in errors[0]


def test_validate_resource_missing_required_field():
    # Observation requires 'code'
    errors = validate_resource({"resourceType": "Observation", "status": "final"})
    assert len(errors) > 0
    assert any("code" in e.lower() for e in errors)


def test_validate_resource_condition_missing_subject():
    errors = validate_resource({"resourceType": "Condition"})
    assert len(errors) > 0
    assert any("subject" in e.lower() for e in errors)


def test_validate_resources_all_valid():
    resources = [
        {"resourceType": "Patient", "id": "p1"},
        {"resourceType": "Patient", "id": "p2"},
    ]
    result = validate_resources(resources)
    assert result.is_valid
    assert result.total == 2
    assert result.valid == 2
    assert result.invalid == 0
    assert result.pass_rate == 1.0


def test_validate_resources_some_invalid():
    resources = [
        {"resourceType": "Patient", "id": "p1"},
        {"resourceType": "Observation", "status": "final"},  # missing code
    ]
    result = validate_resources(resources)
    assert not result.is_valid
    assert result.total == 2
    assert result.valid == 1
    assert result.invalid == 1
    assert result.pass_rate == 0.5
    assert len(result.errors) == 1
    assert result.errors[0]["resourceType"] == "Observation"


def test_validate_resources_empty_list():
    result = validate_resources([])
    assert result.is_valid
    assert result.total == 0


def test_validation_result_defaults():
    vr = ValidationResult()
    assert vr.is_valid
    assert vr.pass_rate == 0.0


def test_validation_result_pass_rate():
    vr = ValidationResult(total=10, valid=8, invalid=2)
    assert vr.pass_rate == 0.8
    assert not vr.is_valid


# ── Choice-type [x] mutual exclusion tests ──────────────────────────


def test_choice_type_single_variant_valid():
    """Setting one deceased[x] variant is valid."""
    resource = {
        "resourceType": "FamilyMemberHistory",
        "id": "fmh1",
        "status": "completed",
        "patient": {"reference": "Patient/p1"},
        "relationship": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-RoleCode", "code": "MTH"}]
        },
        "deceasedBoolean": True,
    }
    errors = _check_choice_type_fields(resource, "FamilyMemberHistory")
    assert errors == []


def test_choice_type_multiple_variants_detected():
    """Setting two deceased[x] variants must produce an error."""
    resource = {
        "resourceType": "FamilyMemberHistory",
        "deceasedBoolean": True,
        "deceasedAge": {"value": 62, "unit": "a", "system": "http://unitsofmeasure.org", "code": "a"},
    }
    errors = _check_choice_type_fields(resource, "FamilyMemberHistory")
    assert len(errors) == 1
    assert "deceased[x]" in errors[0]
    assert "deceasedBoolean" in errors[0]
    assert "deceasedAge" in errors[0]


def test_choice_type_observation_value_conflict():
    """Setting two value[x] variants on Observation must produce an error."""
    resource = {
        "resourceType": "Observation",
        "valueQuantity": {"value": 120, "unit": "mmHg"},
        "valueString": "normal",
    }
    errors = _check_choice_type_fields(resource, "Observation")
    assert len(errors) == 1
    assert "value[x]" in errors[0]


def test_choice_type_none_values_ignored():
    """None values should not count as set."""
    resource = {
        "resourceType": "FamilyMemberHistory",
        "deceasedBoolean": None,
        "deceasedAge": {"value": 62, "unit": "a", "system": "http://unitsofmeasure.org", "code": "a"},
    }
    errors = _check_choice_type_fields(resource, "FamilyMemberHistory")
    assert errors == []


def test_choice_type_unknown_resource_type():
    """Unknown resource types should return no errors."""
    errors = _check_choice_type_fields({"resourceType": "FakeResource"}, "FakeResource")
    assert errors == []


def test_choice_type_patient_deceased():
    """Patient deceased[x] should also be checked."""
    resource = {
        "resourceType": "Patient",
        "deceasedBoolean": True,
        "deceasedDateTime": "2024-01-15",
    }
    errors = _check_choice_type_fields(resource, "Patient")
    assert len(errors) == 1
    assert "deceased[x]" in errors[0]


def test_validate_resource_catches_choice_type_conflict():
    """validate_resource should catch choice-type conflicts early."""
    resource = {
        "resourceType": "FamilyMemberHistory",
        "id": "fmh1",
        "status": "completed",
        "patient": {"reference": "Patient/p1"},
        "relationship": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-RoleCode", "code": "MTH"}]
        },
        "deceasedBoolean": True,
        "deceasedAge": {"value": 62, "unit": "a", "system": "http://unitsofmeasure.org", "code": "a"},
    }
    errors = validate_resource(resource)
    assert len(errors) > 0
    assert any("deceased[x]" in e for e in errors)
