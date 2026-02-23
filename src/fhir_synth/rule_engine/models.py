"""Pydantic models for rules and rulesets."""

from typing import Any

from pydantic import BaseModel, Field


class Rule(BaseModel):
    """Single rule for resource generation."""

    name: str = Field(description="Rule name")
    description: str = Field(description="What this rule does")
    conditions: dict[str, Any] = Field(default_factory=dict, description="Conditions to check")
    actions: dict[str, Any] = Field(default_factory=dict, description="Actions to execute")
    weight: float = Field(default=1.0, ge=0.0, description="Probability weight for this rule")


class RuleSet(BaseModel):
    """Collection of rules for a resource type.

    ``resource_type`` is validated against all known FHIR R4B types.
    """

    resource_type: str = Field(description="FHIR resource type (e.g., Patient, Condition)")
    description: str = Field(description="What resources this ruleset generates")
    rules: list[Rule] = Field(default_factory=list, description="List of rules")
    default_rule: Rule | None = Field(
        default=None, description="Default rule if no conditions match"
    )
    bundle_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Config for bundling multiple resources",
    )

