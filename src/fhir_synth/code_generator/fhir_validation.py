"""FHIR resource validation using fhir.resources Pydantic models.

Validates that generated resource dicts are structurally valid FHIR R4B
by round-tripping them through the ``fhir.resources`` Pydantic models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fhir_synth.fhir_spec import get_resource_class



@dataclass
class ValidationResult:
    """Result of validating a batch of FHIR resources."""

    total: int = 0
    valid: int = 0
    invalid: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if every resource passed validation."""
        return self.invalid == 0

    @property
    def pass_rate(self) -> float:
        """Fraction of resources that passed (0.0–1.0)."""
        return self.valid / self.total if self.total else 0.0


def validate_resource(resource: dict[str, Any]) -> list[str]:
    """Validate a single FHIR resource dict against its Pydantic model.

    Args:
        resource: FHIR resource dictionary (must include ``resourceType``).

    Returns:
        List of error messages. Empty list means the resource is valid.
    """
    resource_type = resource.get("resourceType")
    if not resource_type:
        return ["Missing 'resourceType' key"]

    try:
        cls = get_resource_class(resource_type)
    except ValueError:
        return [f"Unknown resource type: {resource_type}"]

    try:
        cls.model_validate(resource)
        return []
    except Exception as exc:
        # Pydantic ValidationError has .errors() with structured info
        if hasattr(exc, "errors"):
            return [
                f"{'.'.join(str(loc) for loc in e.get('loc', []))}: {e.get('msg', str(e))}"
                for e in exc.errors()
            ]
        return [str(exc)]


def validate_resources(resources: list[dict[str, Any]]) -> ValidationResult:
    """Validate a list of FHIR resource dicts.

    Each resource is independently validated against its ``fhir.resources``
    Pydantic model. Validation errors are collected (not raised) so the
    caller can decide how to handle them.

    Args:
        resources: List of FHIR resource dicts.

    Returns:
        class:`ValidationResult` with counts and error details.
    """
    result = ValidationResult(total=len(resources))

    for i, resource in enumerate(resources):
        errors = validate_resource(resource)
        if errors:
            result.invalid += 1
            resource_type = resource.get("resourceType", "Unknown")
            resource_id = resource.get("id", f"index-{i}")
            result.errors.append(
                {
                    "index": i,
                    "resourceType": resource_type,
                    "id": resource_id,
                    "errors": errors,
                }
            )
        else:
            result.valid += 1


    return result
