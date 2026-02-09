"""Validation module for reference integrity and timeline rules."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fhir_synth.generator import EntityGraph
from fhir_synth.plan import DatasetPlan


class ValidationError(Exception):
    """Validation error."""

    pass


class ValidationResult:
    """Result of validation."""

    def __init__(self) -> None:
        """Initialize result."""
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)

    @property
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """Get a summary of validation results."""
        lines = []
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
            for err in self.errors[:10]:  # Show first 10
                lines.append(f"  - {err}")
            if len(self.errors) > 10:
                lines.append(f"  ... and {len(self.errors) - 10} more")

        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
            for warn in self.warnings[:10]:
                lines.append(f"  - {warn}")
            if len(self.warnings) > 10:
                lines.append(f"  ... and {len(self.warnings) - 10} more")

        if not self.errors and not self.warnings:
            lines.append("Validation passed: no errors or warnings")

        return "\n".join(lines)


def validate_dataset(graph: EntityGraph, plan: DatasetPlan) -> ValidationResult:
    """Validate complete dataset."""
    result = ValidationResult()

    if plan.validation.enforce_reference_integrity:
        _validate_reference_integrity(graph, result)

    if plan.validation.enforce_timeline_rules:
        _validate_timeline_rules(graph, plan, result)

    if plan.validation.med_dispense_after_request:
        _validate_med_dispense_ordering(graph, result)

    if plan.validation.documentreference_binary_linked:
        _validate_document_binary_links(graph, result)

    return result


def _validate_reference_integrity(graph: EntityGraph, result: ValidationResult) -> None:
    """Validate that all references resolve to existing resources."""
    for key, resource in graph.resources.items():
        # Convert to dict if it's a Pydantic model
        resource_dict = resource.dict() if hasattr(resource, "dict") else resource
        # Check all fields for Reference objects
        _check_references_in_dict(resource_dict, graph, result, key)


def _check_references_in_dict(
    obj: Any, graph: EntityGraph, result: ValidationResult, source_key: str
) -> None:
    """Recursively check references in a dictionary."""
    if isinstance(obj, dict):
        if "reference" in obj:
            # This is a Reference object
            ref = obj["reference"]
            if "/" in ref:
                ref_type, ref_id = ref.split("/", 1)
                target = graph.get(ref_type, ref_id)
                if target is None:
                    result.add_error(f"{source_key}: Reference to {ref} does not resolve")
        else:
            # Recursively check nested dicts
            for value in obj.values():
                _check_references_in_dict(value, graph, result, source_key)
    elif isinstance(obj, list):
        for item in obj:
            _check_references_in_dict(item, graph, result, source_key)


def _validate_timeline_rules(
    graph: EntityGraph, plan: DatasetPlan, result: ValidationResult
) -> None:
    """Validate timeline constraints."""
    start_date = datetime.fromisoformat(plan.time.start_date) if plan.time.start_date else None
    end_date = datetime.fromisoformat(plan.time.end_date) if plan.time.end_date else None

    if not start_date or not end_date:
        return

    # Check all resources with date/datetime fields
    for key, resource in graph.resources.items():
        # Convert to dict if it's a Pydantic model
        resource_dict = resource.dict() if hasattr(resource, "dict") else resource
        _check_dates_in_resource(resource_dict, start_date, end_date, result, key)


def _check_dates_in_resource(
    resource: dict[str, Any],
    start_date: datetime,
    end_date: datetime,
    result: ValidationResult,
    key: str,
) -> None:
    """Check dates in resource are within bounds."""
    date_fields = [
        "date",
        "authoredOn",
        "effectiveDateTime",
        "performedDateTime",
        "onsetDateTime",
        "whenHandedOver",
        "birthDate",
    ]

    for field in date_fields:
        if field in resource:
            date_str = resource[field]
            try:
                if "T" in date_str:
                    # DateTime
                    dt = datetime.fromisoformat(date_str.replace("Z", ""))
                    if dt < start_date or dt > end_date:
                        result.add_error(f"{key}: {field} {date_str} is outside time horizon")
                else:
                    # Date only - convert to datetime for comparison
                    dt = datetime.fromisoformat(date_str)
                    if dt < start_date or dt > end_date:
                        result.add_error(f"{key}: {field} {date_str} is outside time horizon")
            except (ValueError, AttributeError):
                result.add_warning(f"{key}: Could not parse date field {field}")


def _validate_med_dispense_ordering(graph: EntityGraph, result: ValidationResult) -> None:
    """Validate that medication dispenses occur after requests."""
    dispenses = graph.get_all("MedicationDispense")

    for dispense in dispenses:
        # Convert to dict if it's a Pydantic model
        dispense_dict = dispense.dict() if hasattr(dispense, "dict") else dispense
        auth_prescriptions = dispense_dict.get("authorizingPrescription", [])
        dispense_date_str = dispense_dict.get("whenHandedOver")

        if not dispense_date_str:
            continue

        try:
            dispense_dt = datetime.fromisoformat(dispense_date_str.replace("Z", ""))
        except (ValueError, AttributeError):
            continue

        for prescription_ref in auth_prescriptions:
            if isinstance(prescription_ref, dict):
                ref = prescription_ref.get("reference", "")
                if ref.startswith("MedicationRequest/"):
                    req_id = ref.split("/")[1]
                    request = graph.get("MedicationRequest", req_id)

                    if request:
                        # Convert to dict if it's a Pydantic model
                        request_dict = request.dict() if hasattr(request, "dict") else request
                        request_date_str = request_dict.get("authoredOn")
                        if request_date_str:
                            try:
                                request_dt = datetime.fromisoformat(
                                    request_date_str.replace("Z", "")
                                )
                                if dispense_dt < request_dt:
                                    result.add_error(
                                        f"MedicationDispense/{dispense.id}: "
                                        f"Dispense date {dispense_date_str} is before "
                                        f"request date {request_date_str}"
                                    )
                            except (ValueError, AttributeError):
                                pass


def _validate_document_binary_links(graph: EntityGraph, result: ValidationResult) -> None:
    """Validate that DocumentReferences link to existing Binaries."""
    doc_refs = graph.get_all("DocumentReference")

    for doc_ref in doc_refs:
        # Convert to dict if it's a Pydantic model
        doc_ref_dict = doc_ref.dict() if hasattr(doc_ref, "dict") else doc_ref
        content_list = doc_ref_dict.get("content", [])
        for content in content_list:
            attachment = content.get("attachment", {})
            binary_url = attachment.get("url", "")

            if binary_url.startswith("Binary/"):
                binary_id = binary_url.split("/")[1]
                binary = graph.get("Binary", binary_id)

                if binary is None:
                    result.add_error(
                        f"DocumentReference/{doc_ref.id}: "
                        f"Binary reference {binary_url} does not resolve"
                    )
