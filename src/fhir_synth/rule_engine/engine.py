"""Rule execution engine."""

import random
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fhir_synth.rule_engine.models import MetaConfig, Rule, RuleSet


class RuleEngine:
    """Executes rules to generate FHIR resources."""

    def __init__(self) -> None:
        """Initialize the rule engine."""
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
                resource = self._default_executor(rule, context, resource_type)

            # Apply metadata from ruleset and rule
            self._apply_metadata(resource, ruleset, rule)

            results.append(resource)

        return results

    def _select_rule(self, ruleset: RuleSet, context: dict[str, Any]) -> Rule:
        """Select the appropriate rule based on conditions."""

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

    @staticmethod
    def _check_conditions(conditions: dict[str, Any], context: dict[str, Any]) -> bool:
        """Check if all conditions are met."""
        for key, expected_value in conditions.items():
            if context.get(key) != expected_value:
                return False
        return True

    @staticmethod
    def _default_executor(
        rule: Rule, context: dict[str, Any], resource_type: str
    ) -> dict[str, Any]:
        """Default executor — builds a resource dict from rule actions.

        Always sets ``resourceType`` from the ruleset so the output is a
        valid FHIR resource skeleton regardless of what the rule specifies.
        """
        resource: dict[str, Any] = {
            "resourceType": resource_type,
            "id": context.get("id", str(uuid.uuid4())),
        }
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
            resource_type: Expected resourceType for all bundled resources
            resources: List of resources to bundle
            bundle_type: Bundle type (transaction, batch, searchset, etc.)

        Returns:
            FHIR Bundle resource
        """
        for resource in resources:
            if resource.get("resourceType") != resource_type:
                raise ValueError(
                    "All resources must match resource_type; "
                    f"expected '{resource_type}', got '{resource.get('resourceType')}'"
                )
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
        return str(uuid.uuid4())

    @staticmethod
    def _current_timestamp() -> str:
        """Get the current timestamp in ISO format."""

        return datetime.now(UTC).isoformat()

    @staticmethod
    def _apply_metadata(
        resource: dict[str, Any], ruleset: RuleSet, rule: Rule
    ) -> None:
        """Apply metadata configuration to a resource.

        Merges global_meta from ruleset and meta from rule.
        Rule-level metadata takes precedence over ruleset-level.

        Args:
            resource: The resource dict to modify
            ruleset: The ruleset containing global_meta
            rule: The rule containing rule-specific meta
        """
        # Collect all metadata configs (global first, then rule-specific)
        meta_configs: list[MetaConfig] = []
        if ruleset.global_meta:
            meta_configs.append(ruleset.global_meta)
        if rule.meta:
            meta_configs.append(rule.meta)

        if not meta_configs:
            return

        # Initialize meta if it doesn't exist
        meta = resource.setdefault("meta", {})

        # Apply each config in order (later ones override earlier ones)
        for config in meta_configs:
            if config.security:
                # Merge security labels
                existing = meta.get("security", [])
                meta["security"] = existing + config.security

            if config.tag:
                # Merge tags
                existing = meta.get("tag", [])
                meta["tag"] = existing + config.tag

            if config.profile:
                # Merge profiles
                existing = meta.get("profile", [])
                meta["profile"] = existing + config.profile

            if config.source:
                meta["source"] = config.source

            if config.versionId:
                meta["versionId"] = config.versionId

            if config.lastUpdated:
                meta["lastUpdated"] = config.lastUpdated

