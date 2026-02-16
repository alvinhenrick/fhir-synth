"""Rule engine for declarative FHIR resource generation."""

from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, Field


class Rule(BaseModel):
    """Single rule for resource generation."""

    name: str = Field(description="Rule name")
    description: str = Field(description="What this rule does")
    conditions: dict[str, Any] = Field(default_factory=dict, description="Conditions to check")
    actions: dict[str, Any] = Field(default_factory=dict, description="Actions to execute")
    weight: float = Field(default=1.0, ge=0.0, description="Probability weight for this rule")


class RuleSet(BaseModel):
    """Collection of rules for a resource type."""

    resource_type: str = Field(description="FHIR resource type (e.g., Patient, Condition)")
    description: str = Field(description="What resources this ruleset generates")
    rules: list[Rule] = Field(default_factory=list, description="List of rules")
    default_rule: Rule | None = Field(default=None, description="Default rule if no conditions match")
    bundle_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Config for bundling multiple resources",
    )


class RuleEngine:
    """Executes rules to generate FHIR resources."""

    def __init__(self) -> None:
        """Initialize rule engine."""
        self.rulesets: dict[str, RuleSet] = {}
        self.executors: dict[str, Callable[[Rule, dict[str, Any]], Any]] = {}

    def register_ruleset(self, ruleset: RuleSet) -> None:
        """Register a ruleset for a resource type."""
        self.rulesets[ruleset.resource_type] = ruleset

    def register_executor(
        self, resource_type: str, executor: Callable[[Rule, dict[str, Any]], Any]
    ) -> None:
        """Register a custom executor function for a resource type."""
        self.executors[resource_type] = executor

    def execute(
        self,
        resource_type: str,
        context: dict[str, Any],
        count: int = 1,
    ) -> list[dict[str, Any]]:
        """Execute rules to generate resources.

        Args:
            resource_type: FHIR resource type to generate
            context: Context data for rule evaluation
            count: Number of resources to generate

        Returns:
            List of generated resources
        """
        if resource_type not in self.rulesets:
            raise ValueError(f"No ruleset registered for {resource_type}")

        ruleset = self.rulesets[resource_type]
        executor = self.executors.get(resource_type)
        results = []

        for _ in range(count):
            # Select rule based on conditions and weights
            rule = self._select_rule(ruleset, context)

            # Execute the rule
            if executor:
                resource = executor(rule, context)
            else:
                resource = self._default_executor(rule, context)

            results.append(resource)

        return results

    def _select_rule(self, ruleset: RuleSet, context: dict[str, Any]) -> Rule:
        """Select the appropriate rule based on conditions."""
        import random

        # Filter rules that match conditions
        matching_rules = []
        for rule in ruleset.rules:
            if self._check_conditions(rule.conditions, context):
                matching_rules.append(rule)

        if not matching_rules:
            if ruleset.default_rule:
                return ruleset.default_rule
            elif ruleset.rules:
                return ruleset.rules[0]
            else:
                raise ValueError(f"No rules available for {ruleset.resource_type}")

        # Weighted random selection
        weights = [rule.weight for rule in matching_rules]
        return random.choices(matching_rules, weights=weights, k=1)[0]

    def _check_conditions(self, conditions: dict[str, Any], context: dict[str, Any]) -> bool:
        """Check if all conditions are met."""
        for key, expected_value in conditions.items():
            if context.get(key) != expected_value:
                return False
        return True

    def _default_executor(self, rule: Rule, context: dict[str, Any]) -> dict[str, Any]:
        """Default executor that builds resource from rule actions."""
        resource = {"id": context.get("id"), "resourceType": context.get("resourceType")}
        resource.update(rule.actions)
        return resource

    def generate_bundle(
        self,
        resource_type: str,
        resources: list[dict[str, Any]],
        bundle_type: str = "transaction",
    ) -> dict[str, Any]:
        """Create a FHIR Bundle from resources.

        Args:
            resource_type: Primary resource type in bundle
            resources: List of resources to bundle
            bundle_type: Bundle type (transaction, batch, searchset, etc.)

        Returns:
            FHIR Bundle resource
        """
        bundle_id = self._generate_id()
        bundle_entries = []

        for resource in resources:
            entry = {
                "fullUrl": f"urn:uuid:{self._generate_id()}",
                "resource": resource,
                "request": {
                    "method": "POST",
                    "url": resource.get("resourceType", ""),
                },
            }
            bundle_entries.append(entry)

        bundle = {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": bundle_type,
            "timestamp": self._current_timestamp(),
            "entry": bundle_entries,
        }

        return bundle

    @staticmethod
    def _generate_id() -> str:
        """Generate a unique ID."""
        import uuid

        return str(uuid.uuid4())

    @staticmethod
    def _current_timestamp() -> str:
        """Get the current timestamp in ISO format."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def generate_empi_resources(
        persons: int,
        systems: list[str] | None = None,
        include_organizations: bool = True,
    ) -> list[dict[str, Any]]:
        """Generate EMPI-style Person and Patient resources.

        Each Person is linked to one Patient per source system (EMR). Optionally
        creates Organization resources for each system and links Patients to them.

        Args:
            persons: Number of Person resources to generate
            systems: Source system identifiers (e.g., ["emr1", "emr2"])
            include_organizations: Whether to create Organization resources

        Returns:
            List of FHIR resources (Organization, Person, Patient)
        """
        if persons < 1:
            raise ValueError("persons must be >= 1")

        systems = systems or ["emr1", "emr2"]
        resources: list[dict[str, Any]] = []

        organizations: dict[str, dict[str, Any]] = {}
        if include_organizations:
            for system in systems:
                org_id = f"org-{system}"
                organizations[system] = {
                    "resourceType": "Organization",
                    "id": org_id,
                    "name": system,
                    "identifier": [{"system": "urn:emr", "value": system}],
                }
            resources.extend(organizations.values())

        for i in range(1, persons + 1):
            person_id = f"person-{i}"
            person_links = []
            patient_resources = []

            for system in systems:
                patient_id = f"{system}-patient-{i}"
                patient_resource: dict[str, Any] = {
                    "resourceType": "Patient",
                    "id": patient_id,
                    "identifier": [
                        {"system": f"urn:emr:{system}", "value": patient_id}
                    ],
                }
                if include_organizations:
                    patient_resource["managingOrganization"] = {
                        "reference": f"Organization/{organizations[system]['id']}"
                    }
                patient_resources.append(patient_resource)
                person_links.append({"target": {"reference": f"Patient/{patient_id}"}})

            person_resource = {
                "resourceType": "Person",
                "id": person_id,
                "link": person_links,
            }

            resources.append(person_resource)
            resources.extend(patient_resources)

        return resources


@dataclass
class GenerationRules:
    """Declarative rules for synthetic data generation."""

    population: dict[str, Any] = field(default_factory=dict)
    """Rules for population characteristics"""

    conditions: list[Rule] = field(default_factory=list)
    """Rules for medical conditions"""

    medications: list[Rule] = field(default_factory=list)
    """Rules for medication prescriptions"""

    observations: list[Rule] = field(default_factory=list)
    """Rules for clinical observations"""

    procedures: list[Rule] = field(default_factory=list)
    """Rules for medical procedures"""

    documents: list[Rule] = field(default_factory=list)
    """Rules for clinical documents"""

    custom_rules: dict[str, list[Rule]] = field(default_factory=dict)
    """Custom rules for other resource types"""

    def to_dict(self) -> dict[str, Any]:
        """Convert rules to dictionary."""
        return {
            "population": self.population,
            "conditions": [r.model_dump() for r in self.conditions],
            "medications": [r.model_dump() for r in self.medications],
            "observations": [r.model_dump() for r in self.observations],
            "procedures": [r.model_dump() for r in self.procedures],
            "documents": [r.model_dump() for r in self.documents],
            "custom_rules": {
                k: [r.model_dump() for r in v] for k, v in self.custom_rules.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GenerationRules:
        """Create rules from a dictionary."""
        return cls(
            population=data.get("population", {}),
            conditions=[Rule(**r) for r in data.get("conditions", [])],
            medications=[Rule(**r) for r in data.get("medications", [])],
            observations=[Rule(**r) for r in data.get("observations", [])],
            procedures=[Rule(**r) for r in data.get("procedures", [])],
            documents=[Rule(**r) for r in data.get("documents", [])],
            custom_rules={
                k: [Rule(**r) for r in v] for k, v in data.get("custom_rules", {}).items()
            },
        )

