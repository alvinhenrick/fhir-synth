"""FHIR resource utilities for working with fhir.resources library."""

from fhir_synth.bundle import BundleFactory
from fhir_synth.fhir_utils.factory import FHIRResourceFactory
from fhir_synth.fhir_utils.lazy_map import FHIR_RESOURCE_CLASSES

__all__ = [
    "FHIRResourceFactory",
    "FHIR_RESOURCE_CLASSES",
    "BundleFactory",
]
