"""Tests for US Core must-support field validation."""

from fhir_synth.code_generator.us_core_validation import USCoreResult, validate_us_core

# ── Patient ──────────────────────────────────────────────────────────────────


def test_patient_fully_compliant():
    resources = [
        {
            "resourceType": "Patient",
            "id": "p1",
            "identifier": [{"system": "http://example.org", "value": "12345"}],
            "name": [{"family": "Smith", "given": ["John"]}],
            "gender": "male",
            "birthDate": "1990-01-15",
        }
    ]
    result = validate_us_core(resources)
    assert result.total_checked == 1
    assert result.fully_compliant == 1
    assert not result.has_warnings


def test_patient_missing_fields():
    resources = [{"resourceType": "Patient", "id": "p1"}]
    result = validate_us_core(resources)
    assert result.total_checked == 1
    assert result.fully_compliant == 0
    assert result.has_warnings
    missing = result.warnings[0]["missing_must_support"]
    assert any("identifier" in m for m in missing)
    assert any("name" in m for m in missing)
    assert any("gender" in m for m in missing)
    assert any("birthDate" in m for m in missing)


# ── Observation ──────────────────────────────────────────────────────────────


def test_observation_compliant():
    resources = [
        {
            "resourceType": "Observation",
            "id": "obs1",
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs",
                        }
                    ]
                }
            ],
            "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
            "subject": {"reference": "Patient/p1"},
        }
    ]
    result = validate_us_core(resources)
    assert result.fully_compliant == 1
    assert not result.has_warnings


def test_observation_missing_subject():
    resources = [
        {
            "resourceType": "Observation",
            "id": "obs1",
            "status": "final",
            "category": [{"coding": [{"code": "vital-signs"}]}],
            "code": {"coding": [{"code": "8867-4"}]},
            # subject is missing
        }
    ]
    result = validate_us_core(resources)
    assert result.has_warnings
    missing = result.warnings[0]["missing_must_support"]
    assert any("subject" in m for m in missing)


# ── Condition ────────────────────────────────────────────────────────────────


def test_condition_compliant():
    resources = [
        {
            "resourceType": "Condition",
            "id": "cond1",
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                    }
                ]
            },
            "category": [{"coding": [{"code": "encounter-diagnosis"}]}],
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "44054006"}]},
            "subject": {"reference": "Patient/p1"},
        }
    ]
    result = validate_us_core(resources)
    assert result.fully_compliant == 1


def test_condition_missing_clinical_status():
    resources = [
        {
            "resourceType": "Condition",
            "id": "cond1",
            "category": [{"coding": [{"code": "encounter-diagnosis"}]}],
            "code": {"coding": [{"code": "44054006"}]},
            "subject": {"reference": "Patient/p1"},
        }
    ]
    result = validate_us_core(resources)
    assert result.has_warnings
    missing = result.warnings[0]["missing_must_support"]
    assert any("clinicalStatus" in m for m in missing)


# ── MedicationRequest ────────────────────────────────────────────────────────


def test_medication_request_choice_type_satisfied():
    """medicationCodeableConcept counts as medication[x]."""
    resources = [
        {
            "resourceType": "MedicationRequest",
            "id": "mr1",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [
                    {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": "6809"}
                ]
            },
            "subject": {"reference": "Patient/p1"},
            "authoredOn": "2024-01-15",
            "requester": {"reference": "Practitioner/dr1"},
        }
    ]
    result = validate_us_core(resources)
    assert result.fully_compliant == 1


# ── Resources with no US Core profile ────────────────────────────────────────


def test_unknown_resource_type_skipped():
    resources = [
        {"resourceType": "Organization", "id": "org1", "name": "ACME Hospital"},
        {"resourceType": "Practitioner", "id": "prac1"},
    ]
    result = validate_us_core(resources)
    assert result.total_checked == 0
    assert not result.has_warnings


# ── Mixed batch ──────────────────────────────────────────────────────────────


def test_mixed_batch_compliance_rate():
    resources = [
        # Compliant Patient
        {
            "resourceType": "Patient",
            "id": "p1",
            "identifier": [{"value": "123"}],
            "name": [{"family": "Doe"}],
            "gender": "female",
            "birthDate": "1985-06-20",
        },
        # Non-compliant Condition (missing clinicalStatus)
        {
            "resourceType": "Condition",
            "id": "c1",
            "category": [{"coding": [{"code": "problem-list-item"}]}],
            "code": {"coding": [{"code": "E11.9"}]},
            "subject": {"reference": "Patient/p1"},
        },
    ]
    result = validate_us_core(resources)
    assert result.total_checked == 2
    assert result.fully_compliant == 1
    assert result.compliance_rate == 0.5
    assert result.has_warnings


def test_empty_resources():
    result = validate_us_core([])
    assert isinstance(result, USCoreResult)
    assert result.total_checked == 0
    assert result.compliance_rate == 1.0
    assert not result.has_warnings
