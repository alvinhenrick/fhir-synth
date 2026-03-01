"""FHIR Synth - Dynamic FHIR R4B synthetic data generator."""

from dotenv import load_dotenv

from fhir_synth.fhir_spec import (
    class_to_module,
    data_type_modules,
    get_resource_class,
    import_guide,
    required_fields,
    resource_names,
    spec_summary,
)

__version__ = "1.2.0"

# Load environment variables from .env file at package init
# This ensures API keys and other env vars are available when using as a library
load_dotenv()


__all__ = [
    "__version__",
    "class_to_module",
    "data_type_modules",
    "get_resource_class",
    "import_guide",
    "resource_names",
    "required_fields",
    "spec_summary",
]
