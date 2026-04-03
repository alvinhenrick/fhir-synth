"""FHIR resource validation using fhir.resources Pydantic models.

Validates that generated resource dicts are structurally valid FHIR R4B
by round-tripping them through the `fhir.resources` Pydantic models.

The fhir.resources Pydantic models handle:
- Required field verification
- Type and format validation
- Cardinality constraints (via field validators)

We add on top:
- Choice-type [x] mutual exclusion (with clear error messages for LLM self-healing)
- Reference integrity validation (cross-resource)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError

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

    Validation layers:
    1. Choice-type [x] mutual exclusion (clear error for LLM retries)
    2. Pydantic model validation (required fields, types, cardinality)

    Args:
        resource: FHIR resource dictionary (must include ``resourceType``).
        strict: If True, enables comprehensive validation mode. Default: True.

    Returns:
        List of error messages. Empty list means the resource is valid.
    """
    resource_type: str | None = resource.get("resourceType")
    if not resource_type:
        return ["Missing 'resourceType' key"]

    try:
        cls = get_resource_class(resource_type)
    except ValueError:
        return [f"Unknown resource type: {resource_type}"]

    errors: list[str] = []

    # Step 1: Check choice-type [x] mutual exclusion before Pydantic validation
    # so the error message is clear and actionable for LLM self-healing retries.
    errors.extend(_check_choice_type_fields(resource, resource_type, cls))
    if errors:
        return errors

    # Step 2: Pydantic model validation (handles required fields, types, cardinality)
    try:
        validated_resource = cls.model_validate(
            resource, strict=strict, context={"strict_validation": True}
        )
        # Trigger any additional validators via serialization round-trip
        validated_resource.model_dump()

    except ValidationError as exc:
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
        errs = validate_resource(resource)
        if errs:
            result.invalid += 1
            resource_type = resource.get("resourceType", "Unknown")
            resource_id = resource.get("id", f"index-{i}")
            entry: dict[str, Any] = {
                "index": i,
                "resourceType": resource_type,
                "id": resource_id,
                "errors": errs,
            }
            result.errors.append(entry)
        else:
            result.valid += 1

    # Check referential integrity
    ref_errors = validate_references(resources)
    for ref_err in ref_errors:
        result.invalid += 1
        result.valid -= 1
        result.errors.append(ref_err)

    return result


def validate_references(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check that all internal FHIR References point to an existing resource ID.

    This ensures that e.g. Encounter.subject points to a Patient that
    exists within the same batch.
    """
    # Collect all IDs present in the batch
    existing_ids: set[str] = set()
    for r in resources:
        res_type = r.get("resourceType")
        res_id = r.get("id")
        if res_type and res_id:
            existing_ids.add(f"{res_type}/{res_id}")

    # Check each resource for broken references
    formatted_errors: list[dict[str, Any]] = []
    for i, resource in enumerate(resources):
        res_type = resource.get("resourceType", "Unknown")
        res_id = resource.get("id", f"index-{i}")

        resource_errors = _collect_broken_refs(resource, existing_ids)
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


def _collect_broken_refs(resource: dict[str, Any], existing_ids: set[str]) -> list[str]:
    """Recursively find broken references in a single resource."""
    errors: list[str] = []

    def _walk(obj: Any, p: str) -> None:
        if isinstance(obj, dict):
            ref = obj.get("reference")
            if (
                isinstance(ref, str)
                and "/" in ref
                and not ref.startswith(("http", "https", "urn:"))
            ):
                if ref not in existing_ids:
                    errors.append(f"Broken reference at {p}: {ref}")
            for k, v in obj.items():
                _walk(v, f"{p}.{k}" if p else k)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                _walk(item, f"{p}[{idx}]")

    _walk(resource, "")
    return errors


def _check_choice_type_fields(
    resource: dict[str, Any], resource_type: str, cls: type[BaseModel] | None = None
) -> list[str]:
    """Detect multiple choice-type [x] variants set on the same resource.

    FHIR choice-type fields (e.g. `deceased[x]`, `value[x]`) allow
    exactly ONE type-specific variant per group.  This function dynamically
    discovers the groups from the Pydantic model's `one_of_many` metadata
    so it works for every resource type without hardcoding.

    Args:
        resource: The FHIR resource dictionary.
        resource_type: The resource type (e.g., "FamilyMemberHistory").
        cls: Optional pre-resolved Pydantic model class.

    Returns:
        List of error messages for choice-type violations.
    """
    resolved_cls: type[BaseModel]
    if cls is not None:
        resolved_cls = cls
    else:
        try:
            resolved_cls = get_resource_class(resource_type)
        except ValueError:
            return []

    # Build {group_name: [field_name, ...]} from Pydantic model_fields metadata
    groups: dict[str, list[str]] = defaultdict(list)
    for name, fld in resolved_cls.model_fields.items():
        extra = fld.json_schema_extra
        if not isinstance(extra, dict):
            continue
        group = extra.get("one_of_many")
        if isinstance(group, str):
            groups[group].append(name)

    errors: list[str] = []
    for group_name, fields in groups.items():
        present = [f for f in fields if f in resource and resource[f] is not None]
        if len(present) > 1:
            errors.append(
                f"Choice-type '{group_name}[x]' conflict in {resource_type}: "
                f"fields {present} are all set, but ONLY ONE is allowed. "
                f"Keep the most specific (e.g. {present[-1]}) and remove the rest."
            )
    return errors
