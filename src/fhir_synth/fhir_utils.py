"""FHIR resource utilities for working with fhir.resources library."""

from typing import Any, Type

from pydantic import BaseModel

from fhir.resources.R4B import (
    bundle,
    condition,
    diagnosticreport,
    documentreference,
    encounter,
    location,
    medication,
    medicationdispense,
    medicationrequest,
    observation,
    organization,
    patient,
    person,
    practitioner,
    practitionerrole,
    procedure,
)

# Create resource classes from R4B modules
Bundle = bundle.Bundle
Condition = condition.Condition
DiagnosticReport = diagnosticreport.DiagnosticReport
DocumentReference = documentreference.DocumentReference
Encounter = encounter.Encounter
Location = location.Location
Medication = medication.Medication
MedicationDispense = medicationdispense.MedicationDispense
MedicationRequest = medicationrequest.MedicationRequest
Observation = observation.Observation
Organization = organization.Organization
Patient = patient.Patient
Person = person.Person
Practitioner = practitioner.Practitioner
PractitionerRole = practitionerrole.PractitionerRole
Procedure = procedure.Procedure

# Map resource type names to their FHIR resource classes
FHIR_RESOURCE_CLASSES: dict[str, Type[BaseModel]] = {
    "Person": Person,
    "Patient": Patient,
    "Condition": Condition,
    "Medication": Medication,
    "MedicationRequest": MedicationRequest,
    "MedicationDispense": MedicationDispense,
    "Observation": Observation,
    "Procedure": Procedure,
    "Encounter": Encounter,
    "Organization": Organization,
    "Location": Location,
    "Practitioner": Practitioner,
    "PractitionerRole": PractitionerRole,
    "DiagnosticReport": DiagnosticReport,
    "DocumentReference": DocumentReference,
    "Bundle": Bundle,
}


class FHIRResourceFactory:
    """Factory for creating FHIR resources from dictionaries."""

    @staticmethod
    def create_patient(
        id: str,
        given_name: str = "John",
        family_name: str = "Doe",
        birth_date: str | None = None,
        **kwargs: Any,
    ) -> Patient:
        """Create a FHIR Patient resource.

        Args:
            id: Patient ID
            given_name: First name
            family_name: Last name
            birth_date: Birth date (ISO format)
            **kwargs: Additional Patient fields

        Returns:
            FHIR Patient resource
        """
        data = {
            "id": id,
            "resourceType": "Patient",
            "name": [{"given": [given_name], "family": family_name}],
            **kwargs,
        }
        if birth_date:
            data["birthDate"] = birth_date

        return Patient(**data)

    @staticmethod
    def create_condition(
        id: str,
        code: str,
        patient_id: str,
        system: str = "http://hl7.org/fhir/sid/icd-10-cm",
        **kwargs: Any,
    ) -> Condition:
        """Create a FHIR Condition resource.

        Args:
            id: Condition ID
            code: ICD-10 code
            patient_id: ID of the patient with this condition
            system: Coding system (default: ICD-10-CM)
            **kwargs: Additional Condition fields

        Returns:
            FHIR Condition resource
        """
        data = {
            "id": id,
            "resourceType": "Condition",
            "code": {"coding": [{"code": code, "system": system}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            **kwargs,
        }
        return Condition(**data)

    @staticmethod
    def create_observation(
        id: str,
        code: str,
        patient_id: str,
        value: str | int | float | None = None,
        loinc_code: str = "4548-4",
        **kwargs: Any,
    ) -> Observation:
        """Create a FHIR Observation resource.

        Args:
            id: Observation ID
            code: Code for the observation
            patient_id: ID of the patient
            value: Observation value
            loinc_code: LOINC code (default: glucose)
            **kwargs: Additional Observation fields

        Returns:
            FHIR Observation resource
        """
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

        return Observation(**data)

    @staticmethod
    def create_medication_request(
        id: str,
        medication_code: str,
        patient_id: str,
        status: str = "active",
        **kwargs: Any,
    ) -> MedicationRequest:
        """Create a FHIR MedicationRequest resource.

        Args:
            id: MedicationRequest ID
            medication_code: Code for the medication
            patient_id: ID of the patient
            status: Request status (default: active)
            **kwargs: Additional MedicationRequest fields

        Returns:
            FHIR MedicationRequest resource
        """
        data = {
            "id": id,
            "resourceType": "MedicationRequest",
            "status": status,
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [{"code": medication_code, "system": "http://www.nlm.nih.gov/research/umls/rxnorm"}]
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            **kwargs,
        }
        return MedicationRequest(**data)

    @staticmethod
    def create_bundle(
        bundle_type: str = "transaction",
        entries: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Bundle:
        """Create a FHIR Bundle resource.

        Args:
            bundle_type: Type of bundle (transaction, batch, collection, etc.)
            entries: List of bundle entries
            **kwargs: Additional Bundle fields

        Returns:
            FHIR Bundle resource
        """
        import uuid
        from datetime import datetime, timezone

        data: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "resourceType": "Bundle",
            "type": bundle_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **kwargs,
        }
        if entries:
            data["entry"] = entries

        return Bundle(**data)

    @staticmethod
    def from_dict(resource_type: str, data: dict[str, Any]) -> BaseModel:
        """Create a FHIR resource from a dictionary.

        Args:
            resource_type: FHIR resource type name
            data: Resource data dictionary

        Returns:
            FHIR resource instance

        Raises:
            ValueError: If resource type is not supported
        """
        if resource_type not in FHIR_RESOURCE_CLASSES:
            raise ValueError(
                f"Unsupported resource type: {resource_type}. "
                f"Supported: {', '.join(FHIR_RESOURCE_CLASSES.keys())}"
            )

        resource_class = FHIR_RESOURCE_CLASSES[resource_type]
        return resource_class(**data)

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

    def build(self) -> Bundle:
        """Build the FHIR Bundle.

        Returns:
            Complete FHIR Bundle resource
        """
        bundle = FHIRResourceFactory.create_bundle(
            bundle_type=self.bundle_type,
            entry=self.entries,
            total=len(self.entries),
        )
        return bundle

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
