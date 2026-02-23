"""Bundle factory for building FHIR Bundles with Pydantic models."""

from typing import Any

from pydantic import BaseModel


class BundleFactory:
    """Factory for building FHIR Bundles with Pydantic model resources.

    This class bridges Pydantic models with the bundle builder,
    automatically converting models to dicts.
    """

    def __init__(self, bundle_type: str = "transaction") -> None:
        """Initialize bundle factory.

        Args:
            bundle_type: Type of bundle to create
        """
        self.bundle_type = bundle_type
        self.entries: list[dict[str, Any]] = []

    def add_resource(
        self,
        resource: BaseModel | dict[str, Any],
        method: str = "POST",
    ) -> None:
        """Add a resource to the bundle.

        Args:
            resource: FHIR resource (Pydantic model or dict)
            method: HTTP method (POST, PUT, DELETE, GET)
        """
        # Convert Pydantic model to dict if needed
        if isinstance(resource, BaseModel):
            resource_dict = resource.model_dump(exclude_none=True, by_alias=True)
        else:
            resource_dict = resource

        resource_type = resource_dict.get("resourceType")
        resource_id = resource_dict.get("id")

        url = f"{resource_type}" + (f"/{resource_id}" if resource_id else "")

        entry = {
            "fullUrl": f"urn:uuid:{resource_id}",
            "resource": resource_dict,
            "request": {
                "method": method,
                "url": url,
            },
        }
        self.entries.append(entry)

    def add_resources(
        self,
        resources: list[BaseModel | dict[str, Any]],
        method: str = "POST",
    ) -> None:
        """Add multiple resources to the bundle.

        Args:
            resources: List of FHIR resources
            method: HTTP method for all resources
        """
        for resource in resources:
            self.add_resource(resource, method)

    def build(self) -> dict[str, Any]:
        """Build the FHIR Bundle as a dictionary.

        Returns:
            Complete FHIR Bundle resource as dict
        """
        import uuid
        from datetime import UTC, datetime

        return {
            "resourceType": "Bundle",
            "id": str(uuid.uuid4()),
            "type": self.bundle_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "total": len(self.entries),
            "entry": self.entries,
        }

    def build_pydantic(self) -> BaseModel:
        """Build the bundle and return as Pydantic model.

        Returns:
            Bundle as a Pydantic model
        """
        from fhir_synth.fhir_spec import get_resource_class

        bundle_dict = self.build()
        bundle_class = get_resource_class("Bundle")
        return bundle_class(**bundle_dict)

    def clear(self) -> None:
        """Clear all entries."""
        self.entries = []

