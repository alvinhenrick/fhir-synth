"""Constants for code generation."""

# ── Sandbox constants ─────────────────────────────────────────────────────
# These are used in prompt generation to tell the LLM what modules are
# available.  Actual security enforcement is handled by smolagents.

# Modules that LLM-generated code is allowed to import
ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "uuid",
        "datetime",
        "time",
        "random",
        "math",
        "string",
        "json",
        "copy",
        "collections",
        "itertools",
        "functools",
        "typing",
        "decimal",
        "re",
        "enum",
        "faker",
    }
)

# Module prefixes that are allowed (e.g. fhir.resources.R4B.patient)
ALLOWED_MODULE_PREFIXES: tuple[str, ...] = (
    "dateutil",
    "fhir.resources",
    "pydantic",
)
