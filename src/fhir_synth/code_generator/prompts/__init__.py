"""Prompt management for FHIR code generation.

All prompt content lives in Markdown files organised by concern:

- ``system/`` — engineering rules, sandbox constraints, role definition
- ``clinical/`` — clinician-authored domain knowledge (editable without touching Python)
- ``templates/``— user-facing prompt templates with ``$variable`` placeholders

This module re-exports the **same public API** that ``generator.py`` consumes:

-: data:`SYSTEM_PROMPT`
-: func:`build_code_prompt`
-: func:`build_fix_prompt`
-: func:`build_empi_prompt`
"""

from fhir_synth.code_generator.constants import ALLOWED_MODULE_PREFIXES, ALLOWED_MODULES
from fhir_synth.code_generator.prompts.loader import load_prompt, load_section, render
from fhir_synth.fhir_spec import import_guide, spec_summary

# ── Pre-compute sandbox values (same logic as old prompts.py) ──────────
_ALLOWED_LIST = ", ".join(sorted(ALLOWED_MODULES))
_ALLOWED_PREFIXES = ", ".join(f"{p}.*" for p in ALLOWED_MODULE_PREFIXES)


def _build_system_prompt() -> str:
    """Assemble the full system prompt from Markdown fragments.

    Sections are loaded in order:
      1. system/ — role, sandbox, hard rules, realism, reference map, creation order, step-by-step
      2. clinical/ — all domain knowledge files
    """
    # Load the system section (has $allowed_list / $allowed_prefixes in sandbox.md)
    system_raw = load_section("system")
    system_text = render(
        system_raw,
        allowed_list=_ALLOWED_LIST,
        allowed_prefixes=_ALLOWED_PREFIXES,
    )

    clinical_text = load_section("clinical")

    return f"{system_text}\n\n{clinical_text}"


# ── Module-level constant (built once at import time) ──────────────────
SYSTEM_PROMPT: str = _build_system_prompt()


# ── User-prompt builders ───────────────────────────────────────────────


def build_code_prompt(requirement: str) -> str:
    """Build a prompt for generating Python code.

    Args:
        requirement: Natural language description of resources to generate

    Returns:
        Formatted prompt string
    """
    template = load_prompt("templates/code_prompt.md")
    return render(
        template,
        requirement=requirement,
        fhir_imports=import_guide(),
        fhir_spec=spec_summary(),
    )


def build_fix_prompt(code: str, error: str) -> str:
    """Build a prompt for fixing broken code.

    Args:
        code: The code that failed
        error: The error message / traceback

    Returns:
        Formatted prompt string
    """
    template = load_prompt("templates/fix_prompt.md")
    return render(
        template,
        code=code,
        error=error,
        fhir_imports=import_guide(),
        fhir_spec=spec_summary(),
        allowed_list=_ALLOWED_LIST,
        allowed_prefixes=_ALLOWED_PREFIXES,
    )


def build_empi_prompt(
    user_prompt: str,
    persons: int,
    systems: list[str] | None = None,
    include_organizations: bool = True,
) -> str:
    """Build a prompt that includes EMPI linkage instructions.

    Instead of post-processing EMPI in Python, this tells the LLM to
    generate Person→Patient linkage directly in the code it produces.

    Args:
        user_prompt: Original user prompt
        persons: Number of Person resources
        systems: List of EMR system identifiers
        include_organizations: Whether to include Organization resources

    Returns:
        Augmented prompt with EMPI instructions
    """
    systems = systems or ["emr1", "emr2"]
    orgs_hint = (
        "Create Organization resources for each system and link Patients via managingOrganization."
        if include_organizations
        else "Do not create Organization resources."
    )
    template = load_prompt("templates/empi_prompt.md")
    return render(
        template,
        persons=str(persons),
        systems=", ".join(systems),
        orgs_hint=orgs_hint,
        user_prompt=user_prompt,
    )


__all__ = [
    "SYSTEM_PROMPT",
    "build_code_prompt",
    "build_empi_prompt",
    "build_fix_prompt",
]
