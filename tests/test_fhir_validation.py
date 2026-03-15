"""Tests for FHIR resource validation."""

from fhir_synth.code_generator.fhir_validation import (
    ValidationResult,
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
