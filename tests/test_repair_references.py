"""Tests for repair_references() in fhir_validation."""

from fhir_synth.code_generator.fhir_validation import repair_references, validate_references


def _make_patient(pid: str) -> dict:
    return {"resourceType": "Patient", "id": pid}


def _make_condition(cid: str, patient_ref: str) -> dict:
    return {
        "resourceType": "Condition",
        "id": cid,
        "subject": {"reference": f"Patient/{patient_ref}"},
    }


# ── Single-candidate repair ──────────────────────────────────────────────────


def test_repair_single_patient_fixes_broken_ref():
    resources = [
        _make_patient("correct-id"),
        _make_condition("c1", "wrong-id"),
    ]
    resources, report = repair_references(resources)

    assert report["repaired"] == 1
    assert report["skipped"] == 0
    assert resources[1]["subject"]["reference"] == "Patient/correct-id"


def test_repair_already_valid_ref_unchanged():
    resources = [
        _make_patient("p1"),
        _make_condition("c1", "p1"),
    ]
    resources, report = repair_references(resources)

    assert report["repaired"] == 0
    assert resources[1]["subject"]["reference"] == "Patient/p1"


def test_repair_no_resources_returns_empty_report():
    resources, report = repair_references([])
    assert report["repaired"] == 0
    assert report["skipped"] == 0
    assert resources == []


# ── Ambiguous / multiple candidates ─────────────────────────────────────────


def test_repair_ambiguous_ref_is_skipped():
    """Two patients → cannot determine correct target → skip."""
    resources = [
        _make_patient("p1"),
        _make_patient("p2"),
        _make_condition("c1", "wrong-id"),
    ]
    resources, report = repair_references(resources)

    assert report["repaired"] == 0
    assert report["skipped"] == 1
    # Reference must remain unchanged
    assert resources[2]["subject"]["reference"] == "Patient/wrong-id"


def test_repair_zero_candidates_is_skipped():
    """Reference to Practitioner when no Practitioner exists → skip."""
    resources = [
        _make_patient("p1"),
        {
            "resourceType": "Observation",
            "id": "obs1",
            "performer": [{"reference": "Practitioner/missing"}],
        },
    ]
    resources, report = repair_references(resources)

    assert report["repaired"] == 0
    assert report["skipped"] == 1


# ── Nested references ────────────────────────────────────────────────────────


def test_repair_nested_reference_in_list():
    """References inside arrays (e.g. performer) are also repaired."""
    resources = [
        {"resourceType": "Practitioner", "id": "prac-real"},
        {
            "resourceType": "Observation",
            "id": "obs1",
            "performer": [{"reference": "Practitioner/prac-fake"}],
        },
    ]
    resources, report = repair_references(resources)

    assert report["repaired"] == 1
    assert resources[1]["performer"][0]["reference"] == "Practitioner/prac-real"


# ── External / absolute references left alone ────────────────────────────────


def test_repair_ignores_absolute_urls():
    """http:// references should never be touched."""
    resources = [
        _make_patient("p1"),
        {
            "resourceType": "Observation",
            "id": "obs1",
            "subject": {"reference": "https://example.org/Patient/external"},
        },
    ]
    resources, report = repair_references(resources)

    assert report["repaired"] == 0
    assert resources[1]["subject"]["reference"] == "https://example.org/Patient/external"


def test_repair_ignores_urn_references():
    resources = [
        _make_patient("p1"),
        {
            "resourceType": "Condition",
            "id": "c1",
            "subject": {"reference": "urn:uuid:some-uuid"},
        },
    ]
    resources, report = repair_references(resources)

    assert report["repaired"] == 0


# ── Integration with validate_references ────────────────────────────────────


def test_repair_eliminates_broken_ref_errors():
    """After repair, validate_references should find no errors."""
    resources = [
        _make_patient("real"),
        _make_condition("c1", "typo"),
    ]
    # Before repair
    assert len(validate_references(resources)) == 1

    resources, _ = repair_references(resources)

    # After repair
    assert validate_references(resources) == []


def test_repair_report_details_format():
    resources = [
        _make_patient("new-id"),
        _make_condition("c1", "old-id"),
    ]
    _, report = repair_references(resources)

    assert len(report["details"]) == 1
    detail = report["details"][0]
    assert "Patient/old-id" in detail
    assert "Patient/new-id" in detail
    assert "→" in detail
