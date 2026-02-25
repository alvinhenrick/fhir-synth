"""Constants for code generation."""

from fhir_synth.fhir_spec import resource_names

# Auto-discovered from fhir.resources — covers ALL R4B resource types (~141)
SUPPORTED_RESOURCE_TYPES: list[str] = resource_names()
