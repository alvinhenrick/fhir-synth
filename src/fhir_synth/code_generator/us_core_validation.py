"""Lightweight US Core R4 must-support field validation.

Checks that generated resources satisfy the must-support requirements of the
most common US Core 3.1.1 profiles.  This is intentionally advisory — missing
must-support fields are reported as warnings, not hard errors, because US Core
requires systems to *be able* to populate them, not that every instance must
contain every field.

Supported profiles
------------------
- US Core Patient
- US Core Observation (Vital Signs & Lab Results)
- US Core Condition
- US Core MedicationRequest
- US Core AllergyIntolerance
- US Core Immunization
- US Core Procedure
- US Core DiagnosticReport
- US Core Encounter
"""

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Per-profile must-support field specifications
# ---------------------------------------------------------------------------

# Each entry is (field_path, human_label).
# field_path uses dot-notation for nested checks; a plain name checks the
# top-level key.  A path like "name.family" checks that at least one element
# of the ``name`` list has a ``family`` key.
_PROFILES: dict[str, list[tuple[str, str]]] = {
    "Patient": [
        ("identifier", "identifier (at least one)"),
        ("name", "name (at least one)"),
        ("gender", "gender"),
        ("birthDate", "birthDate"),
    ],
    "Observation": [
        ("status", "status"),
        ("category", "category"),
        ("code", "code (LOINC preferred)"),
        ("subject", "subject (Patient reference)"),
    ],
    "Condition": [
        ("clinicalStatus", "clinicalStatus"),
        ("category", "category"),
        ("code", "code"),
        ("subject", "subject (Patient reference)"),
    ],
    "MedicationRequest": [
        ("status", "status"),
        ("intent", "intent"),
        ("subject", "subject (Patient reference)"),
        ("authoredOn", "authoredOn"),
        ("requester", "requester"),
    ],
    "AllergyIntolerance": [
        ("clinicalStatus", "clinicalStatus"),
        ("verificationStatus", "verificationStatus"),
        ("code", "code"),
        ("patient", "patient (Patient reference)"),
    ],
    "Immunization": [
        ("status", "status"),
        ("vaccineCode", "vaccineCode"),
        ("patient", "patient (Patient reference)"),
        ("primarySource", "primarySource"),
    ],
    "Procedure": [
        ("status", "status"),
        ("code", "code"),
        ("subject", "subject (Patient reference)"),
    ],
    "DiagnosticReport": [
        ("status", "status"),
        ("category", "category"),
        ("code", "code"),
        ("subject", "subject (Patient reference)"),
    ],
    "Encounter": [
        ("status", "status"),
        ("class", "class (v3-ActCode)"),
        ("type", "type"),
        ("subject", "subject (Patient reference)"),
    ],
}

# Choice-type alternatives: if any of these keys is present the requirement
# is satisfied.  Key = canonical field name used in _PROFILES.
_CHOICE_ALTERNATIVES: dict[str, list[str]] = {
    # MedicationRequest.medication[x]
    "medication": ["medicationCodeableConcept", "medicationReference"],
    # Immunization.occurrence[x]
    "occurrence": ["occurrenceDateTime", "occurrenceString"],
    # Observation.effective[x]
    "effective": ["effectiveDateTime", "effectivePeriod", "effectiveTiming", "effectiveInstant"],
    # Observation.value[x]  (dataAbsentReason also satisfies this)
    "value": [
        "valueQuantity",
        "valueCodeableConcept",
        "valueString",
        "valueBoolean",
        "valueInteger",
        "valueRange",
        "valueRatio",
        "valueSampledData",
        "valueTime",
        "valueDateTime",
        "valuePeriod",
        "dataAbsentReason",
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def us_core_must_support_guide() -> str:
    """Compact US Core must-support field reference for LLM prompts.

    Lists every profile's must-support fields so Stage 2 knows which
    *optional* FHIR fields are required by the US Core profile.  Suitable
    for embedding in a system prompt or FHIR guidelines section.
    """
    lines: list[str] = [
        "US CORE R4 MUST-SUPPORT FIELDS",
        "(Include ALL of these fields in every resource of that type)\n",
    ]
    for resource_type, checks in _PROFILES.items():
        field_labels = ", ".join(label for _, label in checks)
        lines.append(f"  {resource_type}: {field_labels}")
    lines.append(
        "\nNote: 'must-support' means the field MUST be populated if the data exists. "
        "For synthetic data, always include all must-support fields."
    )
    return "\n".join(lines)


@dataclass
class USCoreResult:
    """Result of US Core compliance checking for a batch of resources."""

    total_checked: int = 0
    fully_compliant: int = 0
    warnings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def compliance_rate(self) -> float:
        """Fraction of checked resources that are fully compliant (0.0–1.0)."""
        return self.fully_compliant / self.total_checked if self.total_checked else 1.0

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


def validate_us_core(resources: list[dict[str, Any]]) -> USCoreResult:
    """Check US Core must-support field coverage for a list of resources.

    Only resource types that have a corresponding US Core profile in this
    module are checked; others are silently skipped.

    Args:
        resources: Flat list of FHIR resource dicts.

    Returns:
        :class:`USCoreResult` with per-resource warnings.
    """
    result = USCoreResult()

    for i, resource in enumerate(resources):
        res_type = resource.get("resourceType", "")
        profile_checks = _PROFILES.get(res_type)
        if profile_checks is None:
            continue  # No US Core profile defined for this type — skip

        result.total_checked += 1
        missing = _check_profile(resource, profile_checks)

        if missing:
            result.warnings.append(
                {
                    "index": i,
                    "resourceType": res_type,
                    "id": resource.get("id", f"index-{i}"),
                    "missing_must_support": missing,
                }
            )
        else:
            result.fully_compliant += 1

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_profile(
    resource: dict[str, Any],
    checks: list[tuple[str, str]],
) -> list[str]:
    """Return a list of must-support labels that are absent from *resource*."""
    missing: list[str] = []
    for field_path, label in checks:
        if not _field_present(resource, field_path):
            missing.append(label)
    return missing


def _field_present(resource: dict[str, Any], field_path: str) -> bool:
    """Return True if the field (or an acceptable alternative) is present."""
    # Check choice-type alternatives first
    alternatives = _CHOICE_ALTERNATIVES.get(field_path)
    if alternatives:
        return any(_top_level_present(resource, alt) for alt in alternatives)

    # Dot-notation: "name.family" → check that resource["name"] list has
    # at least one element with a "family" key.
    if "." in field_path:
        parent, child = field_path.split(".", 1)
        parent_val = resource.get(parent)
        if isinstance(parent_val, list):
            return any(
                isinstance(item, dict) and item.get(child) not in (None, "", [])
                for item in parent_val
            )
        if isinstance(parent_val, dict):
            return parent_val.get(child) not in (None, "", [])
        return False

    return _top_level_present(resource, field_path)


def _top_level_present(resource: dict[str, Any], key: str) -> bool:
    """Return True if *key* exists in *resource* with a non-empty value."""
    val = resource.get(key)
    if val is None:
        return False
    if isinstance(val, (list, dict, str)) and not val:
        return False
    return True
