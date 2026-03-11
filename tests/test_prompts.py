"""Tests for the prompt management package."""

from fhir_synth.code_generator.prompts import (
    SYSTEM_PROMPT,
    build_code_prompt,
    build_empi_prompt,
    build_fix_prompt,
)
from fhir_synth.code_generator.prompts.loader import load_prompt, load_section, render

# ── Loader ────────────────────────────────────────────────────────────────


class TestLoader:
    def test_load_prompt_returns_string(self):
        text = load_prompt("system/01_role.md")
        assert isinstance(text, str)
        assert len(text) > 0

    def test_load_section_system(self):
        text = load_section("system")
        assert "HARD RULES" in text
        assert "SANDBOX CONSTRAINTS" in text

    def test_load_section_clinical(self):
        text = load_section("clinical")
        assert "COMORBIDITY" in text
        assert "PATIENT VARIATION" in text

    def test_render_substitutes_variables(self):
        result = render("Hello $name, you are $role", name="Alice", role="admin")
        assert result == "Hello Alice, you are admin"

    def test_render_safe_leaves_unknown_placeholders(self):
        result = render("Hello $name, keep $unknown", name="Alice")
        assert result == "Hello Alice, keep $unknown"


# ── SYSTEM_PROMPT ─────────────────────────────────────────────────────────


class TestSystemPrompt:
    def test_is_nonempty_string(self):
        assert isinstance(SYSTEM_PROMPT, str)
        assert len(SYSTEM_PROMPT) > 1000

    def test_contains_role(self):
        assert "FHIR R4B" in SYSTEM_PROMPT

    def test_contains_sandbox_rendered(self):
        assert "SANDBOX CONSTRAINTS" in SYSTEM_PROMPT
        # Placeholder should have been rendered
        assert "$allowed_list" not in SYSTEM_PROMPT
        # Actual module names should be present
        assert "uuid" in SYSTEM_PROMPT

    def test_contains_hard_rules(self):
        assert "HARD RULES" in SYSTEM_PROMPT
        assert "generate_resources()" in SYSTEM_PROMPT

    def test_contains_realism_guidelines(self):
        assert "REALISM GUIDELINES" in SYSTEM_PROMPT
        assert "Faker" in SYSTEM_PROMPT

    def test_contains_clinical_sections(self):
        assert "PATIENT VARIATION" in SYSTEM_PROMPT
        assert "SOCIAL DETERMINANTS" in SYSTEM_PROMPT
        assert "COMORBIDITY" in SYSTEM_PROMPT
        assert "MEDICATION REALISM" in SYSTEM_PROMPT
        assert "VITAL SIGNS" in SYSTEM_PROMPT
        assert "ENCOUNTER REALISM" in SYSTEM_PROMPT
        assert "ALLERGY INTOLERANCE" in SYSTEM_PROMPT
        assert "IMMUNIZATION" in SYSTEM_PROMPT
        assert "CARE PLAN" in SYSTEM_PROMPT
        assert "DIAGNOSTIC REPORT" in SYSTEM_PROMPT
        assert "EDGE CASES" in SYSTEM_PROMPT
        assert "COVERAGE" in SYSTEM_PROMPT
        assert "PROVENANCE" in SYSTEM_PROMPT

    def test_empi_not_in_system_prompt(self):
        """EMPI instructions must NOT leak into the default system prompt."""
        assert "EMPI" not in SYSTEM_PROMPT
        assert "Person.link" not in SYSTEM_PROMPT

    def test_contains_reference_map(self):
        assert "REFERENCE FIELD MAP" in SYSTEM_PROMPT

    def test_contains_creation_order(self):
        assert "CREATION ORDER" in SYSTEM_PROMPT

    def test_contains_step_by_step(self):
        assert "THINK STEP-BY-STEP" in SYSTEM_PROMPT


# ── build_code_prompt ─────────────────────────────────────────────────────


class TestBuildCodePrompt:
    def test_includes_requirement(self):
        result = build_code_prompt("10 diabetic patients")
        assert "10 diabetic patients" in result

    def test_includes_fhir_spec(self):
        result = build_code_prompt("5 patients")
        assert "FHIR SPEC" in result

    def test_includes_example(self):
        result = build_code_prompt("5 patients")
        assert "EXAMPLE" in result
        assert "generate_resources" in result


# ── build_fix_prompt ──────────────────────────────────────────────────────


class TestBuildFixPrompt:
    def test_includes_error(self):
        result = build_fix_prompt("bad code", "ImportError: nope")
        assert "ImportError: nope" in result

    def test_includes_code(self):
        result = build_fix_prompt("print('hi')", "SyntaxError")
        assert "print('hi')" in result

    def test_includes_sandbox_constraints(self):
        result = build_fix_prompt("x", "err")
        assert "SANDBOX CONSTRAINTS" in result


# ── build_empi_prompt ─────────────────────────────────────────────────────


class TestBuildEmpiPrompt:
    def test_includes_user_prompt(self):
        result = build_empi_prompt("10 diabetic patients", persons=3)
        assert "10 diabetic patients" in result

    def test_includes_persons_and_systems(self):
        result = build_empi_prompt("test", persons=5, systems=["emr1", "lab"])
        assert "5" in result
        assert "emr1" in result
        assert "lab" in result

    def test_includes_org_hint(self):
        result = build_empi_prompt("test", persons=1, include_organizations=True)
        assert "Organization" in result

    def test_no_orgs_hint(self):
        result = build_empi_prompt("test", persons=1, include_organizations=False)
        assert "Do not create Organization" in result

    def test_default_systems(self):
        result = build_empi_prompt("test", persons=1)
        assert "emr1" in result
        assert "emr2" in result
