"""Tests for the prompts markdown loader package."""

from __future__ import annotations

import pytest

from fhir_synth.code_generator.prompts import (
    RULE_NAMES,
    clinical_rules,
    get_rule,
)


def test_clinical_rules_loads_all_sections():
    """clinical_rules() returns all clinician-authored sections."""
    rules = clinical_rules()
    assert len(rules) > 10_000, "combined rules should be substantial"
    # Spot-check key headings from different markdown files
    assert "# Hard Rules" in rules
    assert "# Comorbidity" in rules
    assert "# Medication Realism" in rules
    assert "# Vital Signs" in rules
    assert "# Reference Field Map" in rules


def test_get_rule_returns_individual_section():
    """get_rule() loads a single markdown file by stem name."""
    section = get_rule("comorbidity")
    assert "Metabolic syndrome" in section
    assert "ICD-10" in section


@pytest.mark.parametrize("name", RULE_NAMES)
def test_get_rule_all_names(name: str):
    """Every declared rule name is loadable."""
    section = get_rule(name)
    assert len(section) > 100


def test_get_rule_unknown_raises():
    """get_rule() raises for an unknown rule name."""
    with pytest.raises(FileNotFoundError, match="No rule file"):
        get_rule("nonexistent_rule")


def test_rule_names_list():
    """RULE_NAMES exposes an ordered list of stem names."""
    assert isinstance(RULE_NAMES, list)
    assert len(RULE_NAMES) >= 10
    assert "hard_rules" in RULE_NAMES
    assert "reference_map" in RULE_NAMES


def test_system_prompt_contains_clinical_rules():
    """SYSTEM_PROMPT assembles role + sandbox + rules + step-by-step."""
    from fhir_synth.code_generator.prompts import SYSTEM_PROMPT

    sp = str(SYSTEM_PROMPT)
    assert "FHIR R4B" in sp
    assert "SANDBOX CONSTRAINTS" in sp
    assert "Comorbidity" in sp
    assert "THINK STEP-BY-STEP" in sp


def test_build_code_prompt_includes_requirement():
    """build_code_prompt injects the user requirement."""
    from fhir_synth.code_generator.prompts import build_code_prompt

    prompt = build_code_prompt("5 diabetic patients")
    assert "5 diabetic patients" in prompt
    assert "FHIR SPEC" in prompt


def test_build_fix_prompt_includes_error():
    """build_fix_prompt injects both code and error."""
    from fhir_synth.code_generator.prompts import build_fix_prompt

    prompt = build_fix_prompt("broken code", "ImportError: bad module")
    assert "broken code" in prompt
    assert "ImportError: bad module" in prompt
    assert "SANDBOX CONSTRAINTS" in prompt
