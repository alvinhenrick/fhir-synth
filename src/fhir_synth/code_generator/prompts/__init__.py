"""Prompt package — loads clinician-authored Markdown rules as plain text.

Each ``.md`` file contains clinical rules written by domain experts.
They are loaded with ``Path.read_text()`` and assembled with plain
string concatenation.  No template engine is needed.

For the DSPy code path, these rules are passed as a ``context`` input
field to declarative signatures.  DSPy handles all prompt formatting.

For the non-DSPy code path (``generator.py``), the ``SYSTEM_PROMPT``
and ``build_*`` helpers assemble prompts directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fhir_synth.code_generator.constants import ALLOWED_MODULE_PREFIXES, ALLOWED_MODULES

# ---------------------------------------------------------------------------
# Ordered list of Markdown clinical-rule files
# ---------------------------------------------------------------------------

_PROMPT_DIR = Path(__file__).parent

_RULE_FILES: list[str] = [
    "hard_rules.md",
    "realism_guidelines.md",
    "patient_variation.md",
    "sdoh.md",
    "comorbidity.md",
    "medications.md",
    "vital_signs_labs.md",
    "encounters.md",
    "allergy_immunization.md",
    "careplan_goals.md",
    "diagnostic_documents.md",
    "edge_cases.md",
    "coverage.md",
    "provenance_quality.md",
    "reference_map.md",
]

RULE_NAMES: list[str] = [f.removesuffix(".md") for f in _RULE_FILES]


# ---------------------------------------------------------------------------
# Rule loaders
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def clinical_rules() -> str:
    """Return all clinician-authored rules concatenated in order."""
    sections = [(_PROMPT_DIR / f).read_text(encoding="utf-8") for f in _RULE_FILES]
    return "\n\n---\n\n".join(sections)


def get_rule(name: str) -> str:
    """Return a single clinical-rule section by stem name.

    Args:
        name: Stem name without ``.md`` (e.g. ``"comorbidity"``).

    Raises:
        FileNotFoundError: If the rule file does not exist.
    """
    filename = f"{name}.md"
    if filename not in _RULE_FILES:
        available = ", ".join(RULE_NAMES)
        raise FileNotFoundError(f"No rule file {filename!r}. Available: {available}")
    return (_PROMPT_DIR / filename).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Sandbox section (dynamic — built from constants)
# ---------------------------------------------------------------------------

_ALLOWED_LIST = ", ".join(sorted(ALLOWED_MODULES))
_ALLOWED_PREFIXES = ", ".join(f"{p}.*" for p in ALLOWED_MODULE_PREFIXES)

_SANDBOX_SECTION = (
    "SANDBOX CONSTRAINTS — your code runs in a restricted sandbox:\n"
    f"- ALLOWED imports: {_ALLOWED_LIST}, {_ALLOWED_PREFIXES}\n"
    "- FORBIDDEN builtins: eval(), exec(), open(), compile(), globals(), __import__()\n"
    "- Do NOT use: os, subprocess, socket, shutil, ctypes, threading, "
    "or any module not listed above."
)

# ---------------------------------------------------------------------------
# SYSTEM_PROMPT — used by the non-DSPy generator.py code path
# ---------------------------------------------------------------------------

_ROLE = (
    "You are an expert FHIR R4B synthetic data engineer. You generate Python code\n"
    "that produces clinically realistic, diverse, and valid FHIR R4B resources\n"
    "using the fhir.resources library (Pydantic models)."
)

_THINK_STEP_BY_STEP = (
    "THINK STEP-BY-STEP:\n"
    "1. Parse requirement → identify resource types needed\n"
    "2. Plan imports → check correct module paths (fhir.resources.R4B.{module})\n"
    "3. Design data flow → determine relationships (Patient IDs → references)\n"
    "4. Choose codes → select appropriate ICD-10/LOINC/RxNorm codes\n"
    "5. Implement function → write generate_resources() with proper structure\n"
    "6. Validate → ensure all references are valid, all models use .model_dump()\n"
    "7. EVERY resource dict MUST have a 'resourceType' key.\n\n"
    "Return ONLY the Python code, no explanation text."
)


@lru_cache(maxsize=1)
def _build_system_prompt() -> str:
    return "\n\n".join([_ROLE, _SANDBOX_SECTION, clinical_rules(), _THINK_STEP_BY_STEP])


# ---------------------------------------------------------------------------
# Prompt builders — used by the non-DSPy generator.py code path
# ---------------------------------------------------------------------------


def build_code_prompt(requirement: str) -> str:
    """Build a user prompt for generating Python code."""
    from fhir_synth.fhir_spec import import_guide, spec_summary

    return (
        f"Generate Python code to create FHIR R4B resources.\n\n"
        f"Requirement: {requirement}\n\n"
        f"{import_guide()}\n\n"
        f"FHIR SPEC:\n{spec_summary()}\n\n"
        f"Now generate code for: {requirement}"
    )


def build_fix_prompt(code: str, error: str) -> str:
    """Build a user prompt for fixing broken code."""
    from fhir_synth.fhir_spec import import_guide

    return (
        f"The following Python code failed with this error:\n\n"
        f"ERROR:\n{error}\n\n"
        f"CODE:\n{code}\n\n"
        f"{import_guide()}\n\n"
        f"{_SANDBOX_SECTION}\n\n"
        "Fix the code. Keep the same function signature:\n"
        "  def generate_resources() -> list[dict]:\n"
        "Return ONLY the corrected Python code."
    )


def build_bundle_code_prompt(resource_types: list[str], count_per_resource: int) -> str:
    """Build a user prompt for generating bundle creation code."""
    from fhir_synth.fhir_spec import import_guide, spec_summary

    return (
        f"Generate Python code that creates FHIR R4B resources.\n\n"
        f"Resource types: {', '.join(resource_types)}\n"
        f"Count per type: {count_per_resource}\n\n"
        f"{import_guide(resource_types)}\n\n"
        f"FHIR SPEC:\n{spec_summary(resource_types)}"
    )


def build_rules_prompt(requirement: str) -> str:
    """Build a user prompt for generating rule definitions."""
    return (
        f"Convert this requirement into structured generation rules:\n\n"
        f"{requirement}\n\n"
        'Return JSON with "rules", "resource_type", "bundle_config", '
        '"variation_config" keys.'
    )


# ---------------------------------------------------------------------------
# Module-level init
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = _build_system_prompt()

__all__ = [
    "RULE_NAMES",
    "SYSTEM_PROMPT",
    "_SANDBOX_SECTION",
    "build_bundle_code_prompt",
    "build_code_prompt",
    "build_fix_prompt",
    "build_rules_prompt",
    "clinical_rules",
    "get_rule",
]
