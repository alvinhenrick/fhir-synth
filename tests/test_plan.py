"""Tests for plan schema and validation."""

import pytest

from fhir_synth.plan import (
    DatasetPlan,
    OrganizationConfig,
    OrganizationIdentifier,
    PatientDistribution,
    PopulationConfig,
    SourceSystem,
    TimeConfig,
    TimeHorizon,
)


def test_minimal_plan():
    """Test minimal valid plan."""
    plan = DatasetPlan(
        version=1,
        seed=42,
        population=PopulationConfig(persons=10),
        time=TimeConfig(horizon=TimeHorizon(years=1)),
    )

    assert plan.seed == 42
    assert plan.population.persons == 10
    assert plan.time.horizon.years == 1


def test_multi_org_plan():
    """Test multi-org plan with sources."""
    plan = DatasetPlan(
        version=1,
        seed=42,
        population=PopulationConfig(
            persons=50,
            sources=[
                SourceSystem(
                    id="baylor",
                    organization=OrganizationConfig(
                        name="Baylor Health",
                        identifiers=[OrganizationIdentifier(system="urn:org", value="baylor")],
                    ),
                    patient_id_namespace="baylor",
                    weight=0.5,
                ),
                SourceSystem(
                    id="sutter",
                    organization=OrganizationConfig(
                        name="Sutter Health",
                        identifiers=[OrganizationIdentifier(system="urn:org", value="sutter")],
                    ),
                    patient_id_namespace="sutter",
                    weight=0.5,
                ),
            ],
            person_appearance={"systems_per_person_distribution": {1: 0.7, 2: 0.25, 3: 0.05}},
        ),
        time=TimeConfig(horizon=TimeHorizon(years=3)),
    )

    assert len(plan.population.sources) == 2
    assert plan.population.sources[0].id == "baylor"
    assert plan.population.sources[1].id == "sutter"


def test_patient_distribution_fixed():
    """Test fixed patient distribution."""
    dist = PatientDistribution(fixed=2)
    assert dist.fixed == 2
    assert dist.range is None
    assert dist.distribution is None


def test_patient_distribution_range():
    """Test range patient distribution."""
    dist = PatientDistribution(range=(1, 3))
    assert dist.range == (1, 3)


def test_patient_distribution_dict():
    """Test dictionary patient distribution."""
    dist = PatientDistribution(distribution={1: 0.7, 2: 0.3})
    assert dist.distribution == {1: 0.7, 2: 0.3}


def test_patient_distribution_invalid_multiple():
    """Test that only one distribution type can be specified."""
    with pytest.raises(ValueError, match="exactly one"):
        PatientDistribution(fixed=2, range=(1, 3))


def test_patient_distribution_invalid_sum():
    """Test that distribution must sum to 1.0."""
    with pytest.raises(ValueError, match="sum to 1.0"):
        PatientDistribution(distribution={1: 0.5, 2: 0.3})


def test_time_horizon_to_days():
    """Test time horizon conversion."""
    assert TimeHorizon(days=10).to_days() == 10
    assert TimeHorizon(months=2).to_days() == 60
    assert TimeHorizon(years=1).to_days() == 365


def test_plan_yaml_roundtrip(tmp_path):
    """Test YAML save and load."""
    plan = DatasetPlan(
        version=1,
        seed=99,
        population=PopulationConfig(persons=5),
        time=TimeConfig(horizon=TimeHorizon(months=6)),
    )

    yaml_path = tmp_path / "test.yml"
    plan.to_yaml(str(yaml_path))

    loaded = DatasetPlan.from_yaml(str(yaml_path))
    assert loaded.seed == 99
    assert loaded.population.persons == 5
    assert loaded.time.horizon.months == 6


def test_plan_json_roundtrip(tmp_path):
    """Test JSON save and load."""
    plan = DatasetPlan(
        version=1,
        seed=77,
        population=PopulationConfig(persons=15),
        time=TimeConfig(horizon=TimeHorizon(days=90)),
    )

    json_path = tmp_path / "test.json"
    plan.to_json(str(json_path))

    loaded = DatasetPlan.from_json(str(json_path))
    assert loaded.seed == 77
    assert loaded.population.persons == 15
    assert loaded.time.horizon.days == 90
