"""FHIR resource factory for creating resources from dictionaries."""

from typing import Any

from pydantic import BaseModel

from fhir_synth.fhir_spec import get_resource_class


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
        cls: type[BaseModel] = get_resource_class(resource_type)
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
        data: dict[str, Any] = {
            "id": id,
            "resourceType": "Patient",
            "name": [{"given": [given_name], "family": family_name}],
            **kwargs,
        }
        if birth_date:
            data["birthDate"] = birth_date
        cls: type[BaseModel] = get_resource_class("Patient")
        return cls(**data)

    @staticmethod
    def create_condition(
        id: str,
        code: str,
        patient_id: str,
        system: str = "http://hl7.org/fhir/sid/icd-10-cm",
        **kwargs: Any,
    ) -> BaseModel:
        """Create a FHIR Condition resource."""
        data: dict[str, Any] = {
            "id": id,
            "resourceType": "Condition",
            "code": {"coding": [{"code": code, "system": system}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            **kwargs,
        }
        cls: type[BaseModel] = get_resource_class("Condition")
        return cls(**data)

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
        data: dict[str, Any] = {
            "id": id,
            "resourceType": "Observation",
            "status": "final",
            "code": {"coding": [{"code": loinc_code, "system": "http://loinc.org"}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            **kwargs,
        }
        if value is not None:
            data["valueQuantity"] = {"value": value}
        cls: type[BaseModel] = get_resource_class("Observation")
        return cls(**data)

    @staticmethod
    def create_medication_request(
        id: str,
        medication_code: str,
        patient_id: str,
        status: str = "active",
        **kwargs: Any,
    ) -> BaseModel:
        """Create a FHIR MedicationRequest resource."""
        data: dict[str, Any] = {
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
        cls: type[BaseModel] = get_resource_class("MedicationRequest")
        return cls(**data)

    @staticmethod
    def create_bundle(
        bundle_type: str = "transaction",
        entries: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> BaseModel:
        """Create a FHIR Bundle resource."""
        import uuid
        from datetime import UTC, datetime

        data: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "resourceType": "Bundle",
            "type": bundle_type,
            "timestamp": datetime.now(UTC).isoformat(),
            **kwargs,
        }
        if entries:
            data["entry"] = entries
        cls: type[BaseModel] = get_resource_class("Bundle")
        return cls(**data)

    @staticmethod
    def from_dict(resource_type: str, data: dict[str, Any]) -> BaseModel:
        """Create any FHIR resource from a type name and data dict.

        Supports all 141 R4B resource types via auto-discovery.
        """
        cls: type[BaseModel] = get_resource_class(resource_type)
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

