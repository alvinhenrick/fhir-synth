"""FHIR Synth - Deterministic FHIR R4 synthetic data generator."""

from __future__ import annotations

from dotenv import load_dotenv

from fhir_synth.plan import DatasetPlan

__version__ = "0.1.0"

# Load environment variables from the.env file at package init
# This ensures API keys and other env vars are available when using as a library
load_dotenv()


__all__ = ["DatasetPlan", "__version__"]
