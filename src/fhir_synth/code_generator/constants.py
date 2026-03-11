"""Constants for code generation."""

import re

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
        "faker",
    }
)

# Module prefixes that are allowed (e.g. fhir.resources.R4B.patient)
ALLOWED_MODULE_PREFIXES: tuple[str, ...] = (
    "fhir.resources",
    "pydantic",
)

# Dangerous builtins that require no import — the import whitelist cannot
# catch these, so we block them with regex before execution.
DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\beval\s*\("),
    re.compile(r"\bexec\s*\("),
    re.compile(r"\bopen\s*\("),
    re.compile(r"\bcompile\s*\("),
    re.compile(r"\bglobals\s*\("),
    re.compile(r"\b__import__\s*\("),
]
