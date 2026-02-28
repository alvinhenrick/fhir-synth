"""Constants for code generation."""

import re

from fhir_synth.fhir_spec import resource_names

# Auto-discovered from fhir.resources — covers ALL R4B resource types (~141)
SUPPORTED_RESOURCE_TYPES: list[str] = resource_names()

# ── Sandbox security constants ────────────────────────────────────────────

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
    }
)

# Module prefixes that are allowed (e.g. fhir.resources.R4B.patient)
ALLOWED_MODULE_PREFIXES: tuple[str, ...] = (
    "fhir.resources",
    "pydantic",
)

# Dangerous patterns that should never appear in generated code
DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bos\b\.\b(system|popen|exec|remove|rmdir|unlink|rename)\b"),
    re.compile(r"\bsubprocess\b"),
    re.compile(r"\bshutil\b"),
    re.compile(r"\b__subclasses__\b"),
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\bopen\s*\("),
    re.compile(r"\bsocket\b"),
    re.compile(r"\bctypes\b"),
    re.compile(r"\bcompile\s*\("),
    re.compile(r"\bglobals\s*\("),
    re.compile(r"\bsetattr\s*\("),
    re.compile(r"\bdelattr\s*\("),
    re.compile(r"\b__import__\s*\("),
]

