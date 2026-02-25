"""Generic declarative rules for synthetic data generation."""

from dataclasses import dataclass, field
from typing import Any

from fhir_synth.rule_engine.models import Rule


@dataclass
class GenerationRules:
    """Generic declarative rules for synthetic data generation.

    Rules are stored in a single ``rules_by_type`` dict keyed by FHIR
    resource type name (e.g. ``"Patient"``, ``"Immunization"``).
    This supports any of the 141 FHIR R4B resource types.
    """

    population: dict[str, Any] = field(default_factory=dict)
    """High-level population config (e.g. count, demographics)."""

    rules_by_type: dict[str, list[Rule]] = field(default_factory=dict)
    """Rules keyed by FHIR resource type — works for any of the 141 R4B types."""

    def add_rules(self, resource_type: str, rules: list[Rule]) -> None:
        """Add rules for a resource type."""
        self.rules_by_type.setdefault(resource_type, []).extend(rules)

    def get_rules(self, resource_type: str) -> list[Rule]:
        """Get rules for a resource type."""
        return self.rules_by_type.get(resource_type, [])

    @property
    def resource_types(self) -> list[str]:
        """Return all resource types that have rules defined."""
        return list(self.rules_by_type.keys())

    def to_dict(self) -> dict[str, Any]:
        """Convert rules to dictionary."""
        return {
            "population": self.population,
            "rules_by_type": {
                rt: [r.model_dump() for r in rules] for rt, rules in self.rules_by_type.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationRules":
        """Create rules from a dictionary."""
        rules_by_type: dict[str, list[Rule]] = {}
        for rt, rule_list in data.get("rules_by_type", {}).items():
            rules_by_type[rt] = [Rule(**r) for r in rule_list]

        return cls(
            population=data.get("population", {}),
            rules_by_type=rules_by_type,
        )
