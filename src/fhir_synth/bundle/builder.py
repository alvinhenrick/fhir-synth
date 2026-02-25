"""FHIR Bundle builder for combining multiple resources."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fhir_synth.fhir_spec import reference_targets

# Fields that typically hold a Patient reference (subject, patient, etc.)
_PATIENT_REF_FIELDS = ("subject", "patient")


class BundleBuilder:
    """Build FHIR Bundles from generated resources."""

    def __init__(self, bundle_type: str = "transaction") -> None:
        """Initialize bundle builder.

        Args:
            bundle_type: Type of bundle (transaction, batch, searchset, collection, etc.)
        """
        self.bundle_type = bundle_type
        self.entries: list[dict[str, Any]] = []

    def add_resource(
        self,
        resource: dict[str, Any],
        method: str = "POST",
        url: str | None = None,
    ) -> None:
        """Add a resource to the bundle.

        Args:
            resource: FHIR resource dictionary
            method: HTTP method (POST, PUT, DELETE, GET)
            url: Target URL for the request (auto-generated if not provided)
        """
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")

        if url is None:
            url = f"{resource_type}" + (f"/{resource_id}" if resource_id else "")

        entry = {
            "fullUrl": f"urn:uuid:{resource_id or self._generate_id()}",
            "resource": resource,
            "request": {
                "method": method,
                "url": url,
            },
        }

        self.entries.append(entry)

    def add_resources(
        self,
        resources: list[dict[str, Any]],
        method: str = "POST",
    ) -> None:
        """Add multiple resources to the bundle.

        Args:
            resources: List of FHIR resource dictionaries
            method: HTTP method for all resources
        """
        for resource in resources:
            self.add_resource(resource, method)

    def build(self) -> dict[str, Any]:
        """Build and return the bundle.

        Returns:
            Complete FHIR Bundle resource
        """
        bundle = {
            "resourceType": "Bundle",
            "id": self._generate_id(),
            "type": self.bundle_type,
            "timestamp": self._current_timestamp(),
            "total": len(self.entries),
            "entry": self.entries,
        }

        return bundle

    def build_with_relationships(
        self,
        resources_by_type: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Build a bundle with automatic reference linking between resources.

        Args:
            resources_by_type: Dict mapping resource type to list of resources

        Returns:
            Bundle with established references
        """
        # Create a references map
        references: dict[str, list[str]] = {}
        for resource_type, resources in resources_by_type.items():
            references[resource_type] = [
                str(rid) for r in resources if (rid := r.get("id")) is not None
            ]

        # Add resources and establish relationships
        for resource_type, resources in resources_by_type.items():
            for resource in resources:
                self._add_resource_with_refs(resource, references, resource_type)

        return self.build()

    def _add_resource_with_refs(
        self,
        resource: dict[str, Any],
        references: dict[str, list[str]],
        primary_type: str,
    ) -> None:
        """Add resource and inject references where appropriate.

        Uses ``fhir_spec.reference_targets`` to discover which fields on
        *primary_type* accept references, then auto-links to Patient (or
        other available resources) if IDs exist.
        """
        if primary_type != "Patient" and "Patient" in references and references["Patient"]:
            patient_id = references["Patient"][0]
            # Check if this resource type has subject/patient reference fields
            try:
                ref_fields = reference_targets(primary_type)
                for ref_field in _PATIENT_REF_FIELDS:
                    if ref_field in ref_fields and ref_field not in resource:
                        resource[ref_field] = {"reference": f"Patient/{patient_id}"}
                        break
            except ValueError:
                pass

        self.add_resource(resource)

    def clear(self) -> None:
        """Clear all entries from builder."""
        self.entries = []

    @staticmethod
    def _generate_id() -> str:
        """Generate a unique ID."""
        return str(uuid.uuid4())

    @staticmethod
    def _current_timestamp() -> str:
        """Get the current timestamp in ISO format."""
        return datetime.now(UTC).isoformat() + "Z"
