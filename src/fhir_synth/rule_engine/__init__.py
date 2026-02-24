"""Rule engine for declarative FHIR resource generation."""

from fhir_synth.rule_engine.empi import generate_empi_resources
from fhir_synth.rule_engine.engine import RuleEngine
from fhir_synth.rule_engine.models import MetaConfig, Rule, RuleSet
from fhir_synth.rule_engine.rules import GenerationRules

__all__ = [
    "RuleEngine",
    "Rule",
    "RuleSet",
    "MetaConfig",
    "GenerationRules",
    "generate_empi_resources",
]

