"""Tests for the prompt management package."""

import pytest

from fhir_synth.code_generator.prompts import (
    build_code_prompt,
    build_empi_prompt,
    build_fix_prompt,
    get_system_prompt,
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
    assert "AVAILABLE MODULES" in text


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


# ── get_system_prompt ─────────────────────────────────────────────────────


def test_system_prompt_is_nonempty_string():
    prompt = get_system_prompt()
    assert isinstance(prompt, str)
    assert len(prompt) > 1000


def test_system_prompt_contains_role():
    assert "FHIR R4B" in get_system_prompt()


def test_system_prompt_contains_sandbox_rendered():
    prompt = get_system_prompt()
    assert "AVAILABLE MODULES" in prompt
    # Placeholder should have been rendered
    assert "$allowed_list" not in prompt
    # Actual module names should be present
    assert "uuid" in prompt


def test_system_prompt_contains_hard_rules():
    prompt = get_system_prompt()
    assert "HARD RULES" in prompt
    assert "generate_resources()" in prompt


def test_system_prompt_contains_realism_guidelines():
    prompt = get_system_prompt()
    assert "REALISM GUIDELINES" in prompt
    assert "Faker" in prompt


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
    assert section in get_system_prompt()


def test_system_prompt_empi_not_in_system_prompt():
    """EMPI Person/Patient linkage instructions must NOT leak into the default system prompt."""
    prompt = get_system_prompt()
    assert "Person.link" not in prompt
    assert "EMPI linkage" not in prompt


def test_system_prompt_contains_reference_map():
    assert "REFERENCE FIELD MAP" in get_system_prompt()


def test_system_prompt_contains_creation_order():
    assert "CREATION ORDER" in get_system_prompt()


def test_system_prompt_contains_step_by_step():
    assert "THINK STEP-BY-STEP" in get_system_prompt()


def test_system_prompt_respects_fhir_version():
    """get_system_prompt() reads the current FHIR version, not a stale constant."""
    from fhir_synth import fhir_spec

    original = fhir_spec.get_fhir_version()
    try:
        prompt = get_system_prompt()
        assert f"FHIR {original}" in prompt
    finally:
        fhir_spec.set_fhir_version(original)


def test_system_prompt_deprecated_constant():
    """Importing SYSTEM_PROMPT triggers a deprecation warning."""
    import fhir_synth.code_generator.prompts as prompts_mod

    with pytest.warns(DeprecationWarning, match="SYSTEM_PROMPT is deprecated"):
        _ = prompts_mod.SYSTEM_PROMPT


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
