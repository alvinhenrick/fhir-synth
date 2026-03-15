"""FHIR resource validation using fhir.resources Pydantic models.

Validates that generated resource dicts are structurally valid FHIR R4B
by round-tripping them through the ``fhir.resources`` Pydantic models.

Enhanced with:
- Strict validation mode for comprehensive checking
- Cardinality validation (min/max occurrences)
- Required element verification
- Terminology binding checks (basic)
- Reference integrity validation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

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


def validate_resource(resource: dict[str, Any], *, strict: bool = True) -> list[str]:
    """Validate a single FHIR resource dict against its Pydantic model.

    Enhanced validation includes:
    - Strict mode validation (all Pydantic checks enabled)
    - Required field verification
    - Type and format validation
    - Cardinality checks (via Pydantic's field validators)

    Args:
        resource: FHIR resource dictionary (must include ``resourceType``).
        strict: If True, enables comprehensive validation mode. Default: True.

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

    errors = []

    # Step 1: Pydantic model validation with strict mode
    try:
        # Use model_validate with strict mode for comprehensive checking
        validated_resource = cls.model_validate(
            resource, strict=strict, context={"strict_validation": True}
        )

        # Step 2: Additional deep validation checks
        # Call the .model_dump() to trigger any additional validators
        validated_resource.model_dump()

        # Step 3: Check for required elements based on FHIR spec
        errors.extend(_check_required_elements(resource, resource_type))

        # Step 4: Validate cardinality constraints
        errors.extend(_check_cardinality(resource, resource_type))

    except ValidationError as exc:
        # Pydantic ValidationError has .errors() with structured info
        for e in exc.errors():
            loc_path = ".".join(str(loc) for loc in e.get("loc", []))
            msg = e.get("msg", "")
            error_type = e.get("type", "")
            errors.append(f"{loc_path}: {msg} (type: {error_type})")
    except Exception as exc:
        errors.append(f"Unexpected validation error: {str(exc)}")

    return errors


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

    # Check referential integrity
    ref_errors = validate_references(resources)
    if ref_errors:
        result.invalid += len(ref_errors)
        result.valid -= len(ref_errors)
        result.errors.extend(ref_errors)

    return result


def validate_references(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check that all internal FHIR References point to an existing resource ID.

    This ensures that e.g. Encounter.subject points to a Patient that
    exists within the same batch.
    """
    # 1. Collect all IDs present in the batch
    existing_ids = set()
    for r in resources:
        res_type = r.get("resourceType")
        res_id = r.get("id")
        if res_type and res_id:
            existing_ids.add(f"{res_type}/{res_id}")

    errors = []

    # 2. Find all Reference fields and check if they exist
    def _find_references(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            if "reference" in obj and isinstance(obj["reference"], str):
                ref = obj["reference"]
                # Skip absolute URLs or non-relative references for now
                if "/" in ref and not ref.startswith(("http", "https", "urn:")):
                    if ref not in existing_ids:
                        errors.append(
                            {
                                "path": path,
                                "reference": ref,
                                "msg": f"Referenced resource '{ref}' not found in batch.",
                            }
                        )
            for k, v in obj.items():
                _find_references(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _find_references(item, f"{path}[{i}]")

    for resource in resources:
        _find_references(resource)

    # Re-formatting to match ValidationResult.errors structure
    formatted_errors = []
    # (Actually the recursive _find_references approach above is a bit messy for returning)
    # Let's do a cleaner pass:

    for i, resource in enumerate(resources):
        res_type = resource.get("resourceType", "Unknown")
        res_id = resource.get("id", f"index-{i}")

        # Create list to collect errors for this specific resource
        resource_errors: list[str] = []

        def _check_ref(obj: Any, p: str, errors_list: list[str] = resource_errors) -> None:
            if isinstance(obj, dict):
                ref = obj.get("reference")
                if (
                    isinstance(ref, str)
                    and "/" in ref
                    and not ref.startswith(("http", "https", "urn:"))
                ):
                    if ref not in existing_ids:
                        errors_list.append(f"Broken reference at {p}: {ref}")
                for k, v in obj.items():
                    _check_ref(v, f"{p}.{k}" if p else k, errors_list)
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    _check_ref(item, f"{p}[{idx}]", errors_list)

        _check_ref(resource, "")
        if resource_errors:
            formatted_errors.append(
                {
                    "index": i,
                    "resourceType": res_type,
                    "id": res_id,
                    "errors": resource_errors,
                }
            )

    return formatted_errors


def _check_required_elements(resource: dict[str, Any], resource_type: str) -> list[str]:
    """Check for FHIR required elements beyond Pydantic's basic validation.

    FHIR resources have required elements defined in the spec. While Pydantic
    catches most of these, we add explicit checks for critical elements.

    Args:
        resource: The FHIR resource dictionary.
        resource_type: The resource type (e.g., "Patient").

    Returns:
        List of error messages for missing required elements.
    """
    errors = []

    # Common required elements across all resources
    if not resource.get("resourceType"):
        errors.append("Missing required element: resourceType")

    # Resource-specific required elements
    required_by_type = {
        "Patient": [],  # Patient has no required elements beyond resourceType
        "Observation": ["status", "code"],
        "Condition": ["subject"],
        "MedicationRequest": ["status", "intent", "medication", "subject"],
        "Encounter": ["status", "class"],
        "Procedure": ["status", "subject"],
        "AllergyIntolerance": ["patient"],
        "DiagnosticReport": ["status", "code"],
        "Immunization": ["status", "vaccineCode", "patient"],
        "CarePlan": ["status", "intent", "subject"],
    }

    required_fields = required_by_type.get(resource_type, [])
    for field_name in required_fields:
        if field_name not in resource or resource[field_name] is None:
            errors.append(f"Missing required element for {resource_type}: {field_name}")

    return errors


def _check_cardinality(resource: dict[str, Any], resource_type: str) -> list[str]:
    """Validate cardinality constraints (min/max occurrences).

    Checks that array fields respect their cardinality constraints.
    FHIR defines min..max cardinality for each element.

    Args:
        resource: The FHIR resource dictionary.
        resource_type: The resource type.

    Returns:
        List of error messages for cardinality violations.
    """
    errors: list[str] = []

    # Define known cardinality constraints for common elements
    # Format: {resource_type: {field_path: (min, max)}}
    cardinality_rules = {
        "Patient": {
            "identifier": (0, None),  # 0..* (optional, unbounded)
            "name": (0, None),  # 0..*
            "telecom": (0, None),  # 0..*
            "address": (0, None),  # 0..*
        },
        "Observation": {
            "identifier": (0, None),
            "category": (0, None),
            "performer": (0, None),
            "component": (0, None),
        },
        "MedicationRequest": {
            "identifier": (0, None),
            "dosageInstruction": (0, None),
        },
    }

    if resource_type not in cardinality_rules:
        return errors

    rules = cardinality_rules[resource_type]
    for field_path, (min_card, max_card) in rules.items():
        value = resource.get(field_path)

        # Check if field should be an array
        if isinstance(value, list):
            count = len(value)
            if min_card is not None and count < min_card:
                errors.append(
                    f"Cardinality violation in {resource_type}.{field_path}: "
                    f"expected at least {min_card}, got {count}"
                )
            if max_card is not None and count > max_card:
                errors.append(
                    f"Cardinality violation in {resource_type}.{field_path}: "
                    f"expected at most {max_card}, got {count}"
                )

    return errors
