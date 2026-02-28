"""Tests for code generation."""

from fhir_synth.code_generator import CodeGenerator
from fhir_synth.code_generator.constants import SUPPORTED_RESOURCE_TYPES
from fhir_synth.code_generator.executor import fix_common_imports, validate_imports
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
    """If the first code fails, the LLM is asked to fix it and the retry succeeds."""
    bad_code = "def generate_resources():\n    return 1/0  # will fail"
    good_code = "def generate_resources():\n    return [{'resourceType': 'Patient', 'id': 'fixed'}]"

    class _HealingMock(MockLLMProvider):
        """The first call returns bad code, the second call returns fixed code."""

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


# ── fix_common_imports introspection-driven tests ─────────────────────────


def test_fix_common_imports_rewrites_wrong_module():
    """TimingRepeat should be rewritten from 'timingrepeat' to 'timing'."""
    code = "from fhir.resources.R4B.timingrepeat import TimingRepeat\n"
    fixed = fix_common_imports(code)
    assert "from fhir.resources.R4B.timing import TimingRepeat" in fixed
    assert "timingrepeat" not in fixed


def test_fix_common_imports_leaves_correct_imports_unchanged():
    """Already-correct imports should not be modified."""
    code = "from fhir.resources.R4B.patient import Patient\n"
    fixed = fix_common_imports(code)
    assert fixed == code


def test_fix_common_imports_handles_multiple_classes():
    """Multiple classes from the same module should be kept together."""
    code = "from fhir.resources.R4B.timing import Timing, TimingRepeat\n"
    fixed = fix_common_imports(code)
    assert "Timing" in fixed
    assert "TimingRepeat" in fixed
    assert "from fhir.resources.R4B.timing import" in fixed


def test_fix_common_imports_splits_classes_to_different_modules():
    """If classes belong to different modules, split into separate imports."""
    # This is an unlikely but possible LLM mistake: mixing classes from different modules
    code = "from fhir.resources.R4B.wrong import Patient, Coding\n"
    fixed = fix_common_imports(code)
    assert "from fhir.resources.R4B.patient import Patient" in fixed
    assert "from fhir.resources.R4B.coding import Coding" in fixed


def test_fix_common_imports_preserves_non_fhir_imports():
    """Non-fhir imports should be left unchanged."""
    code = "from uuid import uuid4\nimport random\nfrom fhir.resources.R4B.patient import Patient\n"
    fixed = fix_common_imports(code)
    assert "from uuid import uuid4" in fixed
    assert "import random" in fixed


def test_fix_common_imports_handles_unknown_class_gracefully():
    """Unknown classes should be left in their original module."""
    code = "from fhir.resources.R4B.patient import Patient, SomethingWeird\n"
    fixed = fix_common_imports(code)
    assert "Patient" in fixed
    assert "SomethingWeird" in fixed


def test_fix_dosage_import():
    """DosageDoseAndRate in the wrong module should be fixed."""
    code = "from fhir.resources.R4B.dosagedoseandrate import DosageDoseAndRate\n"
    fixed = fix_common_imports(code)
    assert "from fhir.resources.R4B.dosage import DosageDoseAndRate" in fixed


def test_validate_imports_detects_bad_module():
    """validate_imports should detect non-existent modules and suggest fixes."""
    code = "from fhir.resources.R4B.timingrepeat import TimingRepeat\n"
    errors = validate_imports(code)
    assert len(errors) >= 1
    assert any("timingrepeat" in e for e in errors)
    # Should suggest the correct module
    assert any("timing" in e for e in errors)
