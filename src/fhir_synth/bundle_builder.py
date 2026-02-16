"""FHIR Bundle builder for combining multiple resources."""
import uuid
from datetime import datetime, timezone
from typing import Any

from fhir_synth.rule_engine import RuleEngine


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
            references[resource_type] = [r.get("id") for r in resources if r.get("id")]

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

        Args:
            resource: Resource to add
            references: Map of resource type to IDs
            primary_type: Primary resource type
        """
        # Simple reference injection based on resource type
        if primary_type == "Condition" and "Patient" in references:
            if references["Patient"]:
                patient_id = references["Patient"][0]
                resource["subject"] = {"reference": f"Patient/{patient_id}"}

        elif primary_type == "MedicationRequest" and "Patient" in references:
            if references["Patient"]:
                patient_id = references["Patient"][0]
                resource["subject"] = {"reference": f"Patient/{patient_id}"}

        elif primary_type == "Observation" and "Patient" in references:
            if references["Patient"]:
                patient_id = references["Patient"][0]
                resource["subject"] = {"reference": f"Patient/{patient_id}"}

        elif primary_type == "Procedure" and "Patient" in references:
            if references["Patient"]:
                patient_id = references["Patient"][0]
                resource["subject"] = {"reference": f"Patient/{patient_id}"}

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
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat() + "Z"


class BundleManager:
    """Manage creation and validation of FHIR Bundles."""

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        """Initialize bundle manager.

        Args:
            rule_engine: Optional RuleEngine for rule-based generation
        """
        self.rule_engine = rule_engine or RuleEngine()

    def create_bundle_from_rules(
            self,
            rules: dict[str, Any],
            context: dict[str, Any],
            bundle_type: str = "transaction",
    ) -> dict[str, Any]:
        """Create a bundle by executing rules.

        Args:
            rules: Rules configuration
            context: Generation context
            bundle_type: Type of bundle to create

        Returns:
            Generated FHIR Bundle
        """
        builder = BundleBuilder(bundle_type=bundle_type)

        # Execute each rule type
        for rule_key, rule_config in rules.items():
            if isinstance(rule_config, dict) and "count" in rule_config:
                resource_type = rule_config.get("resourceType")
                count = rule_config.get("count", 1)

                if resource_type in self.rule_engine.rulesets:
                    resources = self.rule_engine.execute(resource_type, context, count)
                    builder.add_resources(resources)

        return builder.build()

    def create_multi_patient_bundle(
            self,
            patient_count: int = 5,
            resources_per_patient: dict[str, int] | None = None,
            bundle_type: str = "transaction",
    ) -> dict[str, Any]:
        """Create a bundle with multiple patients and associated resources.

        Args:
            patient_count: Number of patients to generate
            resources_per_patient: Count of each resource type per patient
                Example: {"Condition": 2, "Medication": 3}
            bundle_type: Type of bundle to create

        Returns:
            FHIR Bundle with patients and related resources
        """
        if resources_per_patient is None:
            resources_per_patient = {"Condition": 1, "Observation": 2}

        builder = BundleBuilder(bundle_type=bundle_type)
        patients = []

        # Generate patients
        if "Patient" in self.rule_engine.rulesets:
            patients = self.rule_engine.execute("Patient", {}, patient_count)
            builder.add_resources(patients)

        # Generate related resources
        for patient in patients:
            patient_id = patient.get("id")
            context = {"patient_id": patient_id}

            for resource_type, count in resources_per_patient.items():
                if resource_type in self.rule_engine.rulesets:
                    resources = self.rule_engine.execute(resource_type, context, count)

                    # Inject patient reference
                    for resource in resources:
                        self._add_patient_reference(resource, patient_id)

                    builder.add_resources(resources)

        return builder.build()

    @staticmethod
    def _add_patient_reference(resource: dict[str, Any], patient_id: str) -> None:
        """Add patient reference to a resource.

        Args:
            resource: Resource to modify
            patient_id: ID of the patient
        """
        # Add subject reference for clinical resources
        clinical_types = ["Condition", "Observation", "Procedure", "MedicationRequest"]
        if resource.get("resourceType") in clinical_types:
            resource["subject"] = {"reference": f"Patient/{patient_id}"}

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
