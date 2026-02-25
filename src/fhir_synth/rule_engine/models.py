"""Pydantic models for rules and rulesets."""

from typing import Any

from pydantic import BaseModel, Field


class MetaConfig(BaseModel):
    """Configuration for FHIR resource metadata.

    Allows setting security labels, tags, profiles, and other metadata elements.
    """

    security: list[dict[str, Any]] | None = Field(
        default=None,
        description="Security labels (e.g., confidentiality, sensitivity)",
    )
    tag: list[dict[str, Any]] | None = Field(
        default=None,
        description="Tags for operational/workflow purposes",
    )
    profile: list[str] | None = Field(
        default=None,
        description="Profile URLs this resource claims to conform to",
    )
    source: str | None = Field(
        default=None,
        description="Source system URI",
    )
    versionId: str | None = Field(
        default=None,
        description="Version-specific identifier",
    )
    lastUpdated: str | None = Field(
        default=None,
        description="Last updated timestamp (ISO 8601)",
    )


class Rule(BaseModel):
    """Single rule for resource generation."""

    name: str = Field(description="Rule name")
    description: str = Field(description="What this rule does")
    conditions: dict[str, Any] = Field(default_factory=dict, description="Conditions to check")
    actions: dict[str, Any] = Field(default_factory=dict, description="Actions to execute")
    weight: float = Field(default=1.0, ge=0.0, description="Probability weight for this rule")
    meta: MetaConfig | None = Field(
        default=None,
        description="Custom metadata (security tags, profiles, etc.)",
    )


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
    global_meta: MetaConfig | None = Field(
        default=None,
        description="Global metadata applied to all resources from this ruleset",
    )
