"""FHIR Bundle management."""

from typing import Any


class BundleManager:
    """Manage creation and validation of FHIR Bundles."""

    # noinspection PyMethodMayBeStatic
    def validate_bundle(self, bundle: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate bundle structure.

        Args:
            bundle: Bundle to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        if bundle.get("resourceType") != "Bundle":
            errors.append("Bundle must have resourceType='Bundle'")

        if "type" not in bundle:
            errors.append("Bundle must have a type")

        if "entry" not in bundle:
            errors.append("Bundle must have entries")

        # Check entries
        for i, entry in enumerate(bundle.get("entry", [])):
            if "resource" not in entry:
                errors.append(f"Entry {i} missing 'resource'")
            else:
                resource = entry["resource"]
                if "resourceType" not in resource:
                    errors.append(f"Entry {i} resource missing 'resourceType'")

        return len(errors) == 0, errors
