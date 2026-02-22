"""FHIR resource utilities for working with fhir.resources library."""

from __future__ import annotations

from datetime import UTC
from typing import Any

from pydantic import BaseModel

from fhir_synth.fhir_spec import get_resource_class, resource_names


def _get_fhir_class(name: str) -> type[BaseModel]:
    """Lazy wrapper — only imports the module when first accessed."""
    return get_resource_class(name)  # type: ignore[return-value]


# Dynamic map — resolves on first access via __getitem__, not at import time
class _LazyResourceMap(dict):  # type: ignore[type-arg]
    """Dict that lazily loads FHIR resource classes on first access."""

    def __init__(self) -> None:
        super().__init__()
        self._names = set(resource_names())

    def __contains__(self, key: object) -> bool:
        return key in self._names

    def __getitem__(self, key: str) -> type[BaseModel]:
        if key not in self._names:
            raise KeyError(key)
        if not super().__contains__(key):
            super().__setitem__(key, _get_fhir_class(key))
        return super().__getitem__(key)

    def keys(self):  # type: ignore[override]
        return self._names

    def __iter__(self):  # type: ignore[override]
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._names)


FHIR_RESOURCE_CLASSES: dict[str, type[BaseModel]] = _LazyResourceMap()  # type: ignore[assignment]


class FHIRResourceFactory:
    """Factory for creating FHIR resources from dictionaries.

    All factory methods use ``get_resource_class`` so they support every
    FHIR R4B resource type without hardcoding imports.
    """

    @staticmethod
    def create_resource(resource_type: str, data: dict[str, Any]) -> BaseModel:
        """Create any FHIR resource from a type name and data dict.

        This is the **generic** factory method — it can create any of the
        141 R4B resource types.

        Args:
            resource_type: FHIR resource type name (e.g. "Patient", "Claim")
            data: Resource data dictionary

        Returns:
            FHIR resource Pydantic model instance
        """
        cls = get_resource_class(resource_type)
        data.setdefault("resourceType", resource_type)
        return cls(**data)

    @staticmethod
    def create_patient(
        id: str,
        given_name: str = "John",
        family_name: str = "Doe",
        birth_date: str | None = None,
        **kwargs: Any,
    ) -> BaseModel:
        """Create a FHIR Patient resource."""
        data = {
            "id": id,
            "resourceType": "Patient",
            "name": [{"given": [given_name], "family": family_name}],
            **kwargs,
        }
        if birth_date:
            data["birthDate"] = birth_date
        return get_resource_class("Patient")(**data)

    @staticmethod
    def create_condition(
        id: str,
        code: str,
        patient_id: str,
        system: str = "http://hl7.org/fhir/sid/icd-10-cm",
        **kwargs: Any,
    ) -> BaseModel:
        """Create a FHIR Condition resource."""
        data = {
            "id": id,
            "resourceType": "Condition",
            "code": {"coding": [{"code": code, "system": system}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            **kwargs,
        }
        return get_resource_class("Condition")(**data)

    @staticmethod
    def create_observation(
        id: str,
        code: str,
        patient_id: str,
        value: str | int | float | None = None,
        loinc_code: str = "4548-4",
        **kwargs: Any,
    ) -> BaseModel:
        """Create a FHIR Observation resource."""
        data = {
            "id": id,
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"code": loinc_code, "system": "http://loinc.org"}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            **kwargs,
        }
        if value is not None:
            data["valueQuantity"] = {"value": value}
        return get_resource_class("Observation")(**data)

    @staticmethod
    def create_medication_request(
        id: str,
        medication_code: str,
        patient_id: str,
        status: str = "active",
        **kwargs: Any,
    ) -> BaseModel:
        """Create a FHIR MedicationRequest resource."""
        data = {
            "id": id,
            "resourceType": "MedicationRequest",
            "status": status,
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [
                    {
                        "code": medication_code,
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    }
                ]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            **kwargs,
        }
        return get_resource_class("MedicationRequest")(**data)

    @staticmethod
    def create_bundle(
        bundle_type: str = "transaction",
        entries: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> BaseModel:
        """Create a FHIR Bundle resource."""
        import uuid
        from datetime import datetime

        data: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "resourceType": "Bundle",
            "type": bundle_type,
            "timestamp": datetime.now(UTC).isoformat(),
            **kwargs,
        }
        if entries:
            data["entry"] = entries
        return get_resource_class("Bundle")(**data)

    @staticmethod
    def from_dict(resource_type: str, data: dict[str, Any]) -> BaseModel:
        """Create any FHIR resource from a type name and data dict.

        Supports all 141 R4B resource types via auto-discovery.

        Args:
            resource_type: FHIR resource type name (e.g. "Patient", "Immunization")
            data: Resource data dictionary

        Returns:
            FHIR resource instance

        Raises:
            ValueError: If resource type is not a known FHIR R4B type
        """
        cls = get_resource_class(resource_type)
        return cls(**data)

    @staticmethod
    def to_dict(resource: BaseModel) -> dict[str, Any]:
        """Convert a FHIR resource to a dictionary.

        Args:
            resource: FHIR resource instance

        Returns:
            Dictionary representation
        """
        return resource.model_dump(exclude_none=True, by_alias=True)


class BundleFactory:
    """Factory for building FHIR Bundles with multiple resources."""

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
            resource_dict = FHIRResourceFactory.to_dict(resource)
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

    def build(self) -> BaseModel:
        """Build the FHIR Bundle.

        Returns:
            Complete FHIR Bundle resource
        """
        _bundle = FHIRResourceFactory.create_bundle(
            bundle_type=self.bundle_type,
            entry=self.entries,
            total=len(self.entries),
        )
        return _bundle

    def build_dict(self) -> dict[str, Any]:
        """Build the bundle and return as dictionary.

        Returns:
            Bundle as dictionary
        """
        _bundle = self.build()
        return FHIRResourceFactory.to_dict(_bundle)

    def clear(self) -> None:
        """Clear all entries."""
        self.entries = []
