"""Tests for bundle splitter."""

import json

from fhir_synth.bundle.splitter import (
    split_resources_by_patient,
    write_ndjson,
    write_split_bundles,
)


def test_split_groups_resources_by_patient():
    resources = [
        {"resourceType": "Patient", "id": "p1"},
        {"resourceType": "Patient", "id": "p2"},
        {"resourceType": "Condition", "id": "c1", "subject": {"reference": "Patient/p1"}},
        {"resourceType": "Observation", "id": "o1", "subject": {"reference": "Patient/p2"}},
    ]

    bundles = split_resources_by_patient(resources)

    assert len(bundles) == 2
    # First bundle: Patient p1 + Condition c1
    p1_types = [e["resource"]["resourceType"] for e in bundles[0]["entry"]]
    assert "Patient" in p1_types
    assert "Condition" in p1_types
    # Second bundle: Patient p2 + Observation o1
    p2_types = [e["resource"]["resourceType"] for e in bundles[1]["entry"]]
    assert "Patient" in p2_types
    assert "Observation" in p2_types


def test_split_includes_unlinked_in_every_bundle():
    resources = [
        {"resourceType": "Patient", "id": "p1"},
        {"resourceType": "Patient", "id": "p2"},
        {"resourceType": "Organization", "id": "org1"},  # no patient ref
    ]

    bundles = split_resources_by_patient(resources)

    assert len(bundles) == 2
    # Both bundles should contain the Organization
    for b in bundles:
        types = [e["resource"]["resourceType"] for e in b["entry"]]
        assert "Organization" in types


def test_split_no_patients_returns_single_bundle():
    resources = [
        {"resourceType": "Organization", "id": "org1"},
        {"resourceType": "Practitioner", "id": "pr1"},
    ]

    bundles = split_resources_by_patient(resources)

    assert len(bundles) == 1
    assert bundles[0]["total"] == 2


def test_split_empty_input():
    bundles = split_resources_by_patient([])
    assert bundles == []


def test_split_bundle_type_is_collection():
    resources = [{"resourceType": "Patient", "id": "p1"}]
    bundles = split_resources_by_patient(resources)
    assert bundles[0]["type"] == "collection"


def test_write_split_bundles(tmp_path):
    bundles = [
        {"resourceType": "Bundle", "type": "collection", "entry": []},
        {"resourceType": "Bundle", "type": "collection", "entry": []},
    ]

    paths = write_split_bundles(bundles, tmp_path / "out")

    assert len(paths) == 2
    assert paths[0].name == "patient_001.json"
    assert paths[1].name == "patient_002.json"
    for p in paths:
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["resourceType"] == "Bundle"


def test_write_ndjson(tmp_path):
    bundles = [
        {"resourceType": "Bundle", "type": "collection", "entry": [{"resource": {"id": "p1"}}]},
        {"resourceType": "Bundle", "type": "collection", "entry": [{"resource": {"id": "p2"}}]},
    ]

    path = write_ndjson(bundles, tmp_path / "out.ndjson")

    assert path.exists()
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        data = json.loads(line)
        assert data["resourceType"] == "Bundle"


def test_split_uses_patient_and_beneficiary_fields():
    resources = [
        {"resourceType": "Patient", "id": "p1"},
        {"resourceType": "Claim", "id": "cl1", "patient": {"reference": "Patient/p1"}},
        {"resourceType": "Coverage", "id": "cv1", "beneficiary": {"reference": "Patient/p1"}},
    ]

    bundles = split_resources_by_patient(resources)

    assert len(bundles) == 1
    assert bundles[0]["total"] == 3
