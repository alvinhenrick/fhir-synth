"""Tests for bundle builder."""

from fhir_synth.bundle import BundleBuilder


def test_bundle_builder_creates_bundle():
    builder = BundleBuilder(bundle_type="transaction")
    builder.add_resource({"resourceType": "Patient", "id": "p1"})
    builder.add_resource({"resourceType": "Condition", "id": "c1"})

    bundle = builder.build()

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "transaction"
    assert bundle["total"] == 2
    assert len(bundle["entry"]) == 2
    assert bundle["entry"][0]["resource"]["id"] == "p1"


def test_bundle_builder_adds_request_url():
    builder = BundleBuilder()
    builder.add_resource({"resourceType": "Patient", "id": "p2"})

    bundle = builder.build()

    assert bundle["entry"][0]["request"]["url"] == "Patient/p2"
