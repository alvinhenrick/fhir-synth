"""Prompt management for FHIR code generation.

All prompt content lives in Markdown files organised by concern:

- ``system/`` — engineering rules, sandbox constraints, role definition
- ``skills/``  — modular SKILL.md files (agentskills.io spec) for clinical knowledge
- ``templates/``— user-facing prompt templates with ``$variable`` placeholders

This module re-exports the **same public API** that ``generator.py`` consumes:

-: data:`SYSTEM_PROMPT`
-: func:`build_code_prompt`
-: func:`build_fix_prompt`
-: func:`build_empi_prompt`
-: func:`get_system_prompt`
"""

from __future__ import annotations

import logging
from pathlib import Path

from fhir_synth.code_generator.constants import ALLOWED_MODULE_PREFIXES, ALLOWED_MODULES
from fhir_synth.code_generator.prompts.loader import load_prompt, load_section, render
from fhir_synth.fhir_spec import get_fhir_version, import_guide, spec_summary
from fhir_synth.skills import KeywordSelector, SkillLoader, SkillSelector

logger = logging.getLogger(__name__)

# ── Pre-compute sandbox values (same logic as old prompts.py) ──────────
_ALLOWED_LIST = ", ".join(sorted(ALLOWED_MODULES))
_ALLOWED_PREFIXES = ", ".join(f"{p}.*" for p in ALLOWED_MODULE_PREFIXES)

# ── Module-level skill infrastructure ──────────────────────────────────
_skill_loader: SkillLoader | None = None
_skill_selector: SkillSelector = KeywordSelector()


def configure_skills(
    user_dirs: list[Path] | None = None,
    selector: SkillSelector | None = None,
) -> None:
    """Configure the skills' system.

    Call before generating prompts to set up user skill directories and/or
    swap the selection strategy (e.g. ``FaissSelector``).

    Args:
        user_dirs: User-provided skill directories (higher priority than built-in).
        selector: Selection strategy.  Defaults to :class:`KeywordSelector`.
    """
    global _skill_loader, _skill_selector  # noqa: PLW0603
    _skill_loader = SkillLoader(user_dirs=user_dirs)
    if selector is not None:
        _skill_selector = selector


def _get_skill_loader() -> SkillLoader:
    """Return the module-level skill loader, creating a default if needed."""
    global _skill_loader  # noqa: PLW0603
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    return _skill_loader


def _build_system_prompt(
    fhir_version: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """Assemble the full system prompt from Markdown fragments.

    Sections are loaded in order:
      1. system/ — role, sandbox, hard rules, realism, reference map, creation order, step-by-step
      2. skills — selectively loaded clinical knowledge based on the user prompt

    When *user_prompt* is provided, the skills selector chooses only the
    relevant skills.  Otherwise, **all** skills are included (backward-compatible fallback identical to loading ``clinical/``).

    Args:
        fhir_version: FHIR version to use in prompts. If None, uses current version.
        user_prompt: User's natural-language request (used for skill selection).
    """
    if fhir_version is None:
        fhir_version = get_fhir_version()

    # Load the system section (has $allowed_list / $allowed_prefixes in sandbox.md)
    system_raw = load_section("system")
    system_text = render(
        system_raw,
        allowed_list=_ALLOWED_LIST,
        allowed_prefixes=_ALLOWED_PREFIXES,
        fhir_version=fhir_version,
    )

    # ── Skills-based clinical knowledge (selective loading) ─────────
    loader = _get_skill_loader()
    all_skills = loader.discover()

    if user_prompt is not None and all_skills:
        selected = _skill_selector.select(user_prompt, all_skills)
    else:
        selected = all_skills  # no prompt or empty → load all

    if selected:
        clinical_text = "\n\n".join(s.body for s in selected)
        logger.debug("Loaded %d/%d skills into system prompt", len(selected), len(all_skills))
    else:
        logger.warning("No skills found — system prompt will have no clinical knowledge")
        clinical_text = ""

    return f"{system_text}\n\n{clinical_text}"


def get_system_prompt(user_prompt: str | None = None) -> str:
    """Get the system prompt, optionally with skill selection.

    Args:
        user_prompt: When provided, only relevant skills are loaded.
            When ``None``, all skills are loaded (backward-compatible).
    """
    return _build_system_prompt(user_prompt=user_prompt)


# ── Module-level constant (for backward compatibility) ──────────────────
# This is built once at import time with a default version
SYSTEM_PROMPT: str = _build_system_prompt("R4B")


# ── User-prompt builders ───────────────────────────────────────────────


def build_code_prompt(requirement: str) -> str:
    """Build a prompt for generating Python code.

    Args:
        requirement: Natural language description of resources to generate

    Returns:
        Formatted prompt string
    """
    template = load_prompt("templates/code_prompt.md")
    fhir_version = get_fhir_version()

    # Build example imports dynamically based on the FHIR version
    example_imports = f"""from fhir.resources.{fhir_version}.patient import Patient
from fhir.resources.{fhir_version}.encounter import Encounter
from fhir.resources.{fhir_version}.condition import Condition
from fhir.resources.{fhir_version}.codeableconcept import CodeableConcept
from fhir.resources.{fhir_version}.coding import Coding
from fhir.resources.{fhir_version}.reference import Reference
from fhir.resources.{fhir_version}.period import Period"""

    return render(
        template,
        requirement=requirement,
        fhir_version=fhir_version,
        fhir_imports=import_guide(),
        fhir_spec=spec_summary(),
        example_imports=example_imports,
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
    "configure_skills",
    "get_system_prompt",
]
