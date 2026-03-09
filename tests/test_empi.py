"""Tests for EMPI prompt generation (LLM-driven, no post-processing)."""

from fhir_synth.code_generator.prompts import build_empi_prompt


def test_build_empi_prompt_includes_persons_and_systems():
    result = build_empi_prompt("3 patients", persons=3, systems=["emr1", "emr2"])
    assert "3" in result
    assert "emr1" in result
    assert "emr2" in result
    assert "3 patients" in result


def test_build_empi_prompt_includes_org_hint():
    result = build_empi_prompt("test", persons=1, include_organizations=True)
    assert "Organization" in result
    assert "managingOrganization" in result


def test_build_empi_prompt_no_orgs():
    result = build_empi_prompt("test", persons=1, include_organizations=False)
    assert "Do not create Organization" in result


def test_build_empi_prompt_default_systems():
    result = build_empi_prompt("test", persons=1)
    assert "emr1" in result
    assert "emr2" in result


def test_build_empi_prompt_wraps_user_prompt():
    result = build_empi_prompt("generate diabetic patients", persons=2)
    assert "generate diabetic patients" in result
    assert "Person" in result
    assert "Patient" in result
