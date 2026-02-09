"""Data generation plan schema with multi-org Person/Patient support."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class OrganizationIdentifier(BaseModel):
    """FHIR identifier for an organization."""

    system: str
    value: str


class OrganizationConfig(BaseModel):
    """Configuration for a source organization."""

    name: str
    identifiers: list[OrganizationIdentifier] = Field(default_factory=list)


class SourceSystem(BaseModel):
    """Configuration for a source system that produces Patient records."""

    id: str = Field(description="Unique identifier for this source system")
    organization: OrganizationConfig
    patient_id_namespace: str = Field(description="Namespace for patient IDs from this system")
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Relative weight for sampling (when choosing single system)",
    )


class PatientDistribution(BaseModel):
    """Distribution specification for patients per person."""

    fixed: int | None = Field(default=None, ge=1)
    range: tuple[int, int] | None = Field(default=None)
    distribution: dict[int, float] | None = Field(default=None)

    @model_validator(mode="after")
    def check_exactly_one(self) -> PatientDistribution:
        """Ensure exactly one distribution type is specified."""
        set_fields = sum(
            [
                self.fixed is not None,
                self.range is not None,
                self.distribution is not None,
            ]
        )
        if set_fields != 1:
            raise ValueError("Must specify exactly one of: fixed, range, or distribution")
        return self

    @field_validator("distribution")
    @classmethod
    def validate_distribution(cls, v: dict[int, float] | None) -> dict[int, float] | None:
        """Validate distribution probabilities sum to ~1.0."""
        if v is None:
            return v
        total = sum(v.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Distribution probabilities must sum to 1.0, got {total}")
        return v


class PopulationConfig(BaseModel):
    """Population generation configuration with multi-org support."""

    persons: int = Field(ge=1, description="Number of Person entities to generate")

    sources: list[SourceSystem] = Field(
        default_factory=list,
        description="Source systems that produce Patient records",
    )

    person_appearance: dict[str, Any] = Field(
        default_factory=lambda: {"systems_per_person_distribution": {1: 1.0}},
        description="Configuration for how many source systems each Person appears in",
    )

    allowed_source_combinations: list[list[str]] | None = Field(
        default=None,
        description="Optional list of allowed source system combinations",
    )

    # Legacy support for simple single-system case
    patients_per_person: PatientDistribution | None = Field(
        default=None,
        description="Legacy: simple patient count per person (use sources instead)",
    )

    @field_validator("person_appearance")
    @classmethod
    def validate_person_appearance(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate person appearance configuration."""
        dist = v.get("systems_per_person_distribution", {})
        if dist:
            total = sum(dist.values())
            if not (0.99 <= total <= 1.01):
                raise ValueError(f"systems_per_person_distribution must sum to 1.0, got {total}")
        return v


class TimeHorizon(BaseModel):
    """Time period specification."""

    days: int | None = Field(default=None, ge=1)
    months: int | None = Field(default=None, ge=1)
    years: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def check_exactly_one(self) -> TimeHorizon:
        """Ensure exactly one time unit is specified."""
        set_fields = sum(
            [
                self.days is not None,
                self.months is not None,
                self.years is not None,
            ]
        )
        if set_fields != 1:
            raise ValueError("Must specify exactly one of: days, months, or years")
        return self

    def to_days(self) -> int:
        """Convert horizon to days (approximate for months/years)."""
        if self.days is not None:
            return self.days
        if self.months is not None:
            return self.months * 30
        if self.years is not None:
            return self.years * 365
        raise ValueError("No time unit specified")


class TimeConfig(BaseModel):
    """Time-related configuration."""

    horizon: TimeHorizon
    start_date: str | None = Field(
        default=None,
        description="ISO 8601 date (YYYY-MM-DD), defaults to now - horizon",
    )
    end_date: str | None = Field(
        default=None,
        description="ISO 8601 date (YYYY-MM-DD), defaults to now",
    )
    timezone: str = Field(default="UTC")


class ResourceCountOverride(BaseModel):
    """Override counts for specific resource types."""

    per_patient: dict[str, int] | None = Field(default=None)
    min: int | None = Field(default=None, ge=0)
    max: int | None = Field(default=None, ge=0)


class ResourceConfig(BaseModel):
    """Resource generation configuration."""

    include: list[str] = Field(
        default_factory=lambda: [
            "Person",
            "Patient",
            "Organization",
            "Practitioner",
            "Location",
            "Encounter",
            "Observation",
            "Condition",
            "Procedure",
            "AllergyIntolerance",
            "MedicationRequest",
            "MedicationDispense",
            "CarePlan",
            "DocumentReference",
            "Binary",
        ]
    )
    exclude: list[str] = Field(default_factory=list)
    count_overrides: dict[str, ResourceCountOverride] = Field(default_factory=dict)


class ScenarioConfig(BaseModel):
    """Scenario/use-case configuration."""

    name: str
    weight: float = Field(default=1.0, ge=0.0)
    params: dict[str, Any] = Field(default_factory=dict)


class OutputConfig(BaseModel):
    """Output format configuration."""

    format: Literal["ndjson", "bundle", "files"] = Field(default="ndjson")
    bundle_type: Literal["collection", "transaction"] | None = Field(default=None)
    path: str = Field(default="./output")
    ndjson: dict[str, Any] = Field(default_factory=lambda: {"split_by_resource_type": False})


class ValidationConfig(BaseModel):
    """Validation rules configuration."""

    enforce_reference_integrity: bool = Field(default=True)
    enforce_timeline_rules: bool = Field(default=True)
    med_dispense_after_request: bool = Field(default=True)
    careplan_has_activities: int | None = Field(default=None, ge=0)
    documentreference_binary_linked: bool = Field(default=True)


class DatasetPlan(BaseModel):
    """Complete dataset generation plan."""

    version: int = Field(default=1)
    seed: int = Field(default=42)
    population: PopulationConfig
    time: TimeConfig
    resources: ResourceConfig = Field(default_factory=ResourceConfig)
    scenarios: list[ScenarioConfig] = Field(default_factory=list)
    outputs: OutputConfig = Field(default_factory=OutputConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)

    @classmethod
    def from_yaml(cls, path: str) -> DatasetPlan:
        """Load plan from YAML file."""
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def to_yaml(self, path: str) -> None:
        """Save plan to YAML file."""
        import yaml

        with open(path, "w") as f:
            yaml.safe_dump(
                self.model_dump(mode="json", exclude_none=True),
                f,
                default_flow_style=False,
                sort_keys=False,
            )

    @classmethod
    def from_json(cls, path: str) -> DatasetPlan:
        """Load plan from JSON file."""
        import json

        with open(path) as f:
            data = json.load(f)
        return cls.model_validate(data)

    def to_json(self, path: str) -> None:
        """Save plan to JSON file."""
        import json

        with open(path, "w") as f:
            json.dump(
                self.model_dump(mode="json", exclude_none=True),
                f,
                indent=2,
            )
