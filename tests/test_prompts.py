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

    def test_load_section_clinical_replaced_by_skills(self):
        """Clinical knowledge now comes from skills, not clinical/ directory."""
        from fhir_synth.skills import SkillLoader

        loader = SkillLoader()
        skills = loader.discover()
        assert len(skills) >= 14  # 16 built-in skills
        bodies = "\n".join(s.body for s in skills)
        assert "Comorbidity" in bodies
        assert "Patient Variation" in bodies

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
        assert "Patient Variation" in SYSTEM_PROMPT
        assert "Social Determinants" in SYSTEM_PROMPT
        assert "Comorbidity" in SYSTEM_PROMPT
        assert "Medication Realism" in SYSTEM_PROMPT
        assert "Vital Signs" in SYSTEM_PROMPT
        assert "Encounter Realism" in SYSTEM_PROMPT
        assert "Allergy" in SYSTEM_PROMPT
        assert "Immunization" in SYSTEM_PROMPT
        assert "Care Plan" in SYSTEM_PROMPT
        assert "Diagnostic Report" in SYSTEM_PROMPT
        assert "Edge Cases" in SYSTEM_PROMPT
        assert "Coverage" in SYSTEM_PROMPT
        assert "Provenance" in SYSTEM_PROMPT

    def test_empi_not_in_system_prompt(self):
        """EMPI Person/Patient linkage instructions must NOT leak into the default system prompt."""
        assert "Person.link" not in SYSTEM_PROMPT
        assert "EMPI linkage" not in SYSTEM_PROMPT

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
