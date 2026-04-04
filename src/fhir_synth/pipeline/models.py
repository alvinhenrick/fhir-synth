"""Domain value objects for the two-stage clinical planning pipeline.

All models are immutable Pydantic value objects — no business logic lives here.
They are the ubiquitous language of the Clinical Planning bounded context.
"""

from __future__ import annotations

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
    conditions: list[ClinicalFinding] = Field(default_factory=list)
    medications: list[MedicationEntry] = Field(default_factory=list)
    allergies: list[str] = Field(
        default_factory=list,
        description="Allergy substances, e.g. ['penicillin', 'latex']",
    )
    encounter_type: str = Field(
        default="outpatient",
        description="Primary encounter type for this patient",
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
