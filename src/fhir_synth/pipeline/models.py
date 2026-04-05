"""Domain value objects for the two-stage clinical planning pipeline.

All models are immutable Pydantic value objects — no business logic lives here.
They are the ubiquitous language of the Clinical Planning bounded context.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Coding(BaseModel):
    """A clinical code from a standard terminology system (SNOMED, LOINC, RxNorm, etc.)."""

    model_config = {"frozen": True}

    system: str = Field(description="Terminology system URI, e.g. http://snomed.info/sct")
    code: str = Field(description="Code value within the system")
    display: str = Field(default="", description="Human-readable display name")

    @field_validator("system", "code")
    @classmethod
    def must_be_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be empty")
        return v


class ClinicalFinding(BaseModel):
    """A clinical observation, diagnosis, or problem."""

    model_config = {"frozen": True}

    coding: Coding
    onset_description: str | None = Field(
        default=None,
        description="Natural language onset, e.g. '5 years ago', 'childhood'",
    )
    severity: str | None = Field(
        default=None,
        description="e.g. 'mild', 'moderate', 'severe'",
    )


class MedicationEntry(BaseModel):
    """A medication a patient is taking or has been prescribed."""

    model_config = {"frozen": True}

    rxnorm_code: str = Field(description="RxNorm concept code, e.g. '6809' for Metformin")
    display: str = Field(description="Medication name and strength, e.g. 'Metformin 500mg'")
    dose: str | None = Field(default=None, description="e.g. '500mg', '10 units'")
    frequency: str | None = Field(default=None, description="e.g. 'twice daily', 'every morning'")


class PlannedResource(BaseModel):
    """Any FHIR resource the plan explicitly requests Stage 2 to generate.

    Used for clinical resource types not covered by the typed fields on
    ``PatientProfile`` (conditions, medications, allergies).  Examples:
    Immunization, Procedure, Observation, DiagnosticReport, Encounter,
    Goal, CarePlan, FamilyMemberHistory — anything in the FHIR spec.

    ``resource_type`` is validated against the live ``fhir.resources``
    registry so the set of accepted types grows automatically with the spec.
    """

    model_config = {"frozen": True}

    resource_type: str = Field(
        description=(
            "FHIR resource type to generate, e.g. 'Immunization', 'Procedure', "
            "'Observation', 'DiagnosticReport'. Must be a valid FHIR resource type."
        )
    )
    description: str = Field(
        description=(
            "Natural language description for Stage 2, e.g. "
            "'COVID-19 mRNA vaccine, 2023-06', 'Appendectomy 2 years ago', "
            "'BMI 28.5 kg/m²'. Drives the clinical content of the generated resource."
        )
    )
    coding: Coding | None = Field(
        default=None,
        description="Primary code for the resource (SNOMED, LOINC, CPT, CVX, etc.)",
    )

    @field_validator("resource_type")
    @classmethod
    def resource_type_must_be_valid_fhir(cls, v: str) -> str:
        from fhir_synth.fhir_spec import resource_names

        if v not in resource_names():
            raise ValueError(
                f"{v!r} is not a known FHIR resource type. "
                f"Examples: Immunization, Procedure, Observation, DiagnosticReport, Encounter."
            )
        return v


class CareTeamMember(BaseModel):
    """A care provider that Stage 2 must create as a companion FHIR resource.

    Added by PlanEnricher (Stage 1.5) when it detects that the plan will
    generate resources with mandatory references to providers or organisations.

    ``role`` is any valid FHIR resource type name — validated at construction
    time against the live fhir.resources registry so new FHIR resource types
    are automatically accepted without code changes.
    """

    model_config = {"frozen": True}

    role: str = Field(
        description=(
            "FHIR resource type to create, e.g. 'Practitioner', 'Organization', "
            "'RelatedPerson', 'Device', 'CareTeam'. Must be a valid FHIR resource type."
        )
    )
    display_name: str = Field(description="Provider name, e.g. 'Dr. Smith'")
    specialty: str | None = Field(
        default=None, description="Clinical specialty, e.g. 'Internal Medicine'"
    )
    npi: str | None = Field(default=None, description="National Provider Identifier (10 digits)")

    @field_validator("role")
    @classmethod
    def role_must_be_valid_fhir_resource(cls, v: str) -> str:
        from fhir_synth.fhir_spec import resource_names

        known = resource_names()
        if v not in known:
            raise ValueError(
                f"{v!r} is not a known FHIR resource type. "
                f"Examples: Practitioner, PractitionerRole, Organization, "
                f"RelatedPerson, Device, CareTeam."
            )
        return v


# Valid US Core gender values
_GENDER = Literal["male", "female", "other", "unknown"]


class PatientProfile(BaseModel):
    """A single patient's demographic and clinical snapshot.

    Represents the planned clinical state — not a FHIR Patient resource.
    The code synthesis stage turns this into one.
    """

    model_config = {"frozen": True}

    age: int = Field(ge=0, le=120, description="Age in years at time of encounter")
    gender: _GENDER
    race: str | None = Field(default=None, description="e.g. 'White', 'Black or African American'")
    ethnicity: str | None = Field(
        default=None, description="e.g. 'Hispanic or Latino', 'Not Hispanic or Latino'"
    )
    conditions: list[ClinicalFinding] = Field(
        default_factory=list,
        json_schema_extra={"fhir_resource_type": "Condition"},
    )
    medications: list[MedicationEntry] = Field(
        default_factory=list,
        json_schema_extra={"fhir_resource_type": "MedicationRequest"},
    )
    allergies: list[str] = Field(
        default_factory=list,
        description="Allergy substances, e.g. ['penicillin', 'latex']",
        json_schema_extra={"fhir_resource_type": "AllergyIntolerance"},
    )
    encounter_type: str = Field(
        default="outpatient",
        description="Primary encounter type for this patient",
    )
    resources: list[PlannedResource] = Field(
        default_factory=list,
        description=(
            "Additional FHIR resources to generate for this patient beyond the typed fields. "
            "Use for Immunization, Procedure, Observation, DiagnosticReport, Encounter, "
            "Goal, CarePlan, FamilyMemberHistory, and any other FHIR resource type. "
            "Stage 2 must create one FHIR resource per entry."
        ),
    )


class ClinicalPlan(BaseModel):
    """Structured output of the clinical planning stage.

    This is the contract between Stage 1 (clinical planner) and Stage 2
    (FHIR code synthesizer).  The synthesizer turns this into executable
    Python code that generates FHIR resources.
    """

    model_config = {"frozen": True}

    patients: list[PatientProfile] = Field(
        min_length=1,
        description="One entry per patient to generate",
    )
    care_setting: str = Field(
        description="Clinical environment, e.g. 'outpatient clinic', 'inpatient', 'emergency'"
    )
    encounter_type: str = Field(
        description="Primary encounter type, e.g. 'routine visit', 'follow-up', 'admission'"
    )
    notes: str = Field(
        default="",
        description="Additional code-generation hints, e.g. 'include HbA1c observations'",
    )
    fhir_version: str = Field(default="R4B", description="Target FHIR version: R4B or STU3")
    care_team: list[CareTeamMember] = Field(
        default_factory=list,
        description=(
            "Care providers to create as FHIR resources. "
            "Populated by PlanEnricher to satisfy reference dependencies. "
            "Stage 2 must create a resource for each entry and use it in references."
        ),
    )
