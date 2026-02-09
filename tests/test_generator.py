"""Tests for data generation."""

from fhir_synth.generator import DatasetGenerator
from fhir_synth.plan import (
    DatasetPlan,
    OrganizationConfig,
    OrganizationIdentifier,
    PopulationConfig,
    SourceSystem,
    TimeConfig,
    TimeHorizon,
)


def test_simple_generation():
    """Test simple dataset generation."""
    plan = DatasetPlan(
        version=1,
        seed=42,
        population=PopulationConfig(persons=5),
        time=TimeConfig(horizon=TimeHorizon(months=6)),
    )

    generator = DatasetGenerator(plan)
    graph = generator.generate()

    # Check that resources were created
    assert len(graph.get_all("Person")) == 5
    assert len(graph.get_all("Patient")) == 5
    assert len(graph.get_all("Organization")) > 0
    assert len(graph.get_all("Practitioner")) > 0
    assert len(graph.get_all("Encounter")) > 0


def test_multi_org_generation():
    """Test multi-org dataset generation."""
    plan = DatasetPlan(
        version=1,
        seed=42,
        population=PopulationConfig(
            persons=10,
            sources=[
                SourceSystem(
                    id="org1",
                    organization=OrganizationConfig(
                        name="Org 1",
                        identifiers=[OrganizationIdentifier(system="urn:org", value="org1")],
                    ),
                    patient_id_namespace="org1",
                    weight=0.5,
                ),
                SourceSystem(
                    id="org2",
                    organization=OrganizationConfig(
                        name="Org 2",
                        identifiers=[OrganizationIdentifier(system="urn:org", value="org2")],
                    ),
                    patient_id_namespace="org2",
                    weight=0.5,
                ),
            ],
            person_appearance={"systems_per_person_distribution": {1: 0.5, 2: 0.5}},
        ),
        time=TimeConfig(horizon=TimeHorizon(years=1)),
    )

    generator = DatasetGenerator(plan)
    graph = generator.generate()

    persons = graph.get_all("Person")
    patients = graph.get_all("Patient")

    assert len(persons) == 10
    # With 50/50 distribution of 1 or 2 systems per person, expect 10-20 patients
    assert 10 <= len(patients) <= 20

    # Check that source orgs were created
    orgs = graph.get_all("Organization")
    assert len(orgs) >= 2


def test_deterministic_generation():
    """Test that same seed produces same output."""
    plan1 = DatasetPlan(
        version=1,
        seed=99,
        population=PopulationConfig(persons=3),
        time=TimeConfig(horizon=TimeHorizon(months=3)),
    )

    plan2 = DatasetPlan(
        version=1,
        seed=99,
        population=PopulationConfig(persons=3),
        time=TimeConfig(horizon=TimeHorizon(months=3)),
    )

    gen1 = DatasetGenerator(plan1)
    gen2 = DatasetGenerator(plan2)

    graph1 = gen1.generate()
    graph2 = gen2.generate()

    # Check resource counts match
    for resource_type in graph1.by_type.keys():
        assert len(graph1.by_type[resource_type]) == len(graph2.by_type[resource_type])

    # Check IDs match
    patients1 = graph1.get_all("Patient")
    patients2 = graph2.get_all("Patient")

    assert [p.id for p in patients1] == [p.id for p in patients2]


def test_reference_integrity():
    """Test that all references resolve."""
    plan = DatasetPlan(
        version=1,
        seed=42,
        population=PopulationConfig(persons=5),
        time=TimeConfig(horizon=TimeHorizon(months=6)),
    )

    generator = DatasetGenerator(plan)
    graph = generator.generate()

    # Check Person -> Patient references
    persons = graph.get_all("Person")
    for person in persons:
        links = getattr(person, "link", []) or []
        for link in links:
            target = getattr(link, "target", None)
            if target:
                target_ref = getattr(target, "reference", "")
                if target_ref and target_ref.startswith("Patient/"):
                    patient_id = target_ref.split("/")[1]
                    patient = graph.get("Patient", patient_id)
                    assert patient is not None, f"Person/{person.id} references missing {target_ref}"

    # Check Encounter -> Patient references
    encounters = graph.get_all("Encounter")
    for encounter in encounters:
        subject = getattr(encounter, "subject", None)
        if subject:
            subject_ref = getattr(subject, "reference", "")
            if subject_ref and subject_ref.startswith("Patient/"):
                patient_id = subject_ref.split("/")[1]
                patient = graph.get("Patient", patient_id)
                assert patient is not None, f"Encounter/{encounter.id} references missing {subject_ref}"
