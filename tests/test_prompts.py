"""Tests for the prompt management package."""

import pytest

from fhir_synth.code_generator.prompts import (
    SYSTEM_PROMPT,
    build_code_prompt,
    build_empi_prompt,
    build_fix_prompt,
)
from fhir_synth.code_generator.prompts.loader import load_prompt, load_section, render

# ── Loader ────────────────────────────────────────────────────────────────


def test_load_prompt_returns_string():
    text = load_prompt("system/01_role.md")
    assert isinstance(text, str)
    assert len(text) > 0


def test_load_section_system():
    text = load_section("system")
    assert "HARD RULES" in text
    assert "SANDBOX CONSTRAINTS" in text


def test_load_section_clinical_replaced_by_skills():
    """Clinical knowledge now comes from skills, not clinical/ directory."""
    from fhir_synth.skills import SkillLoader

    loader = SkillLoader()
    skills = loader.discover()
    assert len(skills) >= 14  # 16 built-in skills
    bodies = "\n".join(s.body for s in skills)
    assert "Comorbidity" in bodies
    assert "Patient Variation" in bodies


@pytest.mark.parametrize(
    "template,kwargs,expected",
    [
        (
            "Hello $name, you are $role",
            {"name": "Alice", "role": "admin"},
            "Hello Alice, you are admin",
        ),
        ("Hello $name, keep $unknown", {"name": "Alice"}, "Hello Alice, keep $unknown"),
    ],
)
def test_render(template, kwargs, expected):
    result = render(template, **kwargs)
    assert result == expected


# ── SYSTEM_PROMPT ─────────────────────────────────────────────────────────


def test_system_prompt_is_nonempty_string():
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT) > 1000


def test_system_prompt_contains_role():
    assert "FHIR R4B" in SYSTEM_PROMPT


def test_system_prompt_contains_sandbox_rendered():
    assert "SANDBOX CONSTRAINTS" in SYSTEM_PROMPT
    # Placeholder should have been rendered
    assert "$allowed_list" not in SYSTEM_PROMPT
    # Actual module names should be present
    assert "uuid" in SYSTEM_PROMPT


def test_system_prompt_contains_hard_rules():
    assert "HARD RULES" in SYSTEM_PROMPT
    assert "generate_resources()" in SYSTEM_PROMPT


def test_system_prompt_contains_realism_guidelines():
    assert "REALISM GUIDELINES" in SYSTEM_PROMPT
    assert "Faker" in SYSTEM_PROMPT


@pytest.mark.parametrize(
    "section",
    [
        "Patient Variation",
        "Social Determinants",
        "Comorbidity",
        "Medication Realism",
        "Vital Signs",
        "Encounter Realism",
        "Allergy",
        "Immunization",
        "Care Plan",
        "Diagnostic Report",
        "Edge Cases",
        "Coverage",
        "Provenance",
    ],
)
def test_system_prompt_contains_clinical_section(section):
    assert section in SYSTEM_PROMPT


def test_system_prompt_empi_not_in_system_prompt():
    """EMPI Person/Patient linkage instructions must NOT leak into the default system prompt."""
    assert "Person.link" not in SYSTEM_PROMPT
    assert "EMPI linkage" not in SYSTEM_PROMPT


def test_system_prompt_contains_reference_map():
    assert "REFERENCE FIELD MAP" in SYSTEM_PROMPT


def test_system_prompt_contains_creation_order():
    assert "CREATION ORDER" in SYSTEM_PROMPT


def test_system_prompt_contains_step_by_step():
    assert "THINK STEP-BY-STEP" in SYSTEM_PROMPT


# ── build_code_prompt ─────────────────────────────────────────────────────


def test_build_code_prompt_includes_requirement():
    result = build_code_prompt("10 diabetic patients")
    assert "10 diabetic patients" in result


def test_build_code_prompt_includes_fhir_spec():
    result = build_code_prompt("5 patients")
    assert "FHIR SPEC" in result


def test_build_code_prompt_includes_example():
    result = build_code_prompt("5 patients")
    assert "EXAMPLE" in result
    assert "generate_resources" in result


# ── build_fix_prompt ──────────────────────────────────────────────────────


def test_build_fix_prompt_includes_error():
    result = build_fix_prompt("bad code", "ImportError: nope")
    assert "ImportError: nope" in result


def test_build_fix_prompt_includes_code():
    result = build_fix_prompt("print('hi')", "SyntaxError")
    assert "print('hi')" in result


def test_build_fix_prompt_includes_sandbox_constraints():
    result = build_fix_prompt("x", "err")
    assert "AVAILABLE MODULES" in result


# ── build_empi_prompt ─────────────────────────────────────────────────────


def test_build_empi_prompt_includes_user_prompt():
    result = build_empi_prompt("10 diabetic patients", persons=3)
    assert "10 diabetic patients" in result


def test_build_empi_prompt_includes_persons_and_systems():
    result = build_empi_prompt("test", persons=5, systems=["emr1", "lab"])
    assert "5" in result
    assert "emr1" in result
    assert "lab" in result


def test_build_empi_prompt_includes_org_hint():
    result = build_empi_prompt("test", persons=1, include_organizations=True)
    assert "Organization" in result


def test_build_empi_prompt_no_orgs_hint():
    result = build_empi_prompt("test", persons=1, include_organizations=False)
    assert "Do not create Organization" in result


def test_build_empi_prompt_default_systems():
    result = build_empi_prompt("test", persons=1)
    assert "emr1" in result
    assert "emr2" in result
