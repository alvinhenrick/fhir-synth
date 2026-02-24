"""Tests for code generation."""

from fhir_synth.code_generator import CodeGenerator
from fhir_synth.code_generator.constants import SUPPORTED_RESOURCE_TYPES
from fhir_synth.llm import MockLLMProvider


def test_apply_metadata_to_resources():
    """Test that metadata can be applied to generated resources."""
    resources = [
        {"resourceType": "Patient", "id": "p1"},
        {"resourceType": "Condition", "id": "c1"},
    ]

    security = [{"system": "http://security.org", "code": "N", "display": "Normal"}]
    tag = [{"system": "http://tags.org", "code": "test"}]
    profile = ["http://example.org/StructureDefinition/test"]
    source = "http://test-system.org"

    CodeGenerator.apply_metadata_to_resources(
        resources,
        security=security,
        tag=tag,
        profile=profile,
        source=source,
    )

    for resource in resources:
        assert "meta" in resource
        assert resource["meta"]["security"] == security
        assert resource["meta"]["tag"] == tag
        assert resource["meta"]["profile"] == profile
        assert resource["meta"]["source"] == source


def test_code_generator_extracts_code_block():
    response = """Here is code:\n```python\nprint('hi')\n```\n"""
    llm = MockLLMProvider(response=response)
    code_gen = CodeGenerator(llm)

    code = code_gen.generate_code_from_prompt("test")

    assert "print('hi')" in code


def test_code_generator_executes_generated_code():
    code = """
from fhir.resources.R4B import patient

def generate_resources():
    p = patient.Patient(id='p1', name=[{'given':['A'], 'family':'B'}])
    return [p.model_dump()]
"""
    llm = MockLLMProvider(response=code)
    code_gen = CodeGenerator(llm)

    generated_code = code_gen.generate_code_from_prompt("test")
    resources = code_gen.execute_generated_code(generated_code)

    assert len(resources) == 1
    assert resources[0]["id"] == "p1"


def test_self_healing_retry_fixes_broken_code():
    """If first code fails, the LLM is asked to fix it and the retry succeeds."""
    bad_code = "def generate_resources():\n    return 1/0  # will fail"
    good_code = "def generate_resources():\n    return [{'resourceType': 'Patient', 'id': 'fixed'}]"

    class _HealingMock(MockLLMProvider):
        """First call returns bad code, second call returns fixed code."""

        def __init__(self) -> None:
            super().__init__()
            self._call_count = 0

        def generate_text(self, prompt, system=None, json_schema=None):  # type: ignore[override]
            self._call_count += 1
            if self._call_count <= 1:
                return bad_code
            return good_code

    llm = _HealingMock()
    code_gen = CodeGenerator(llm, max_retries=2)

    generated = code_gen.generate_code_from_prompt("test")
    resources = code_gen.execute_generated_code(generated)

    assert len(resources) == 1
    assert resources[0]["id"] == "fixed"


def test_supported_resource_types_has_no_concatenation_bugs():
    """Ensure every element in the list is a standalone resource type name."""
    for rt in SUPPORTED_RESOURCE_TYPES:
        assert rt[0].isupper(), f"{rt} does not start with uppercase"
        assert " " not in rt, f"{rt} contains a space"
        assert len(rt) < 50, f"{rt} looks like a concatenation bug"
