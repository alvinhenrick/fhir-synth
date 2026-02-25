"""FHIR Bundle management with rule-based generation."""

from typing import Any

from fhir_synth.bundle.builder import BundleBuilder
from fhir_synth.fhir_spec import reference_targets
from fhir_synth.rule_engine import RuleEngine

# Fields that typically hold a Patient reference (subject, patient, etc.)
_PATIENT_REF_FIELDS = ("subject", "patient")


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
        for _rule_key, rule_config in rules.items():
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
            if patient_id is None:
                continue
            patient_id_str = str(patient_id)
            context: dict[str, Any] = {"patient_id": patient_id_str}

            for resource_type, count in resources_per_patient.items():
                if resource_type in self.rule_engine.rulesets:
                    resources = self.rule_engine.execute(resource_type, context, count)

                    # Inject patient reference
                    for resource in resources:
                        self._add_patient_reference(resource, patient_id_str)

                    builder.add_resources(resources)

        return builder.build()

    @staticmethod
    def _add_patient_reference(resource: dict[str, Any], patient_id: str) -> None:
        """Add patient reference to a resource.

        Uses ``fhir_spec.reference_targets`` to discover if the resource
        type has a ``subject`` or ``patient`` field that accepts a reference.
        """
        rt = resource.get("resourceType", "")
        try:
            ref_fields = reference_targets(rt)
            for ref_field in _PATIENT_REF_FIELDS:
                if ref_field in ref_fields:
                    resource[ref_field] = {"reference": f"Patient/{patient_id}"}
                    break
        except ValueError:
            pass

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
