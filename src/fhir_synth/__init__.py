"""FHIR Synth - Deterministic FHIR R4 synthetic data generator."""

from dotenv import load_dotenv

__version__ = "0.1.0"

# Load environment variables from the.env file at package init
# This ensures API keys and other env vars are available when using as a library
load_dotenv()


__all__ = [ "__version__"]
