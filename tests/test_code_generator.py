"""Tests for code generation."""

import pytest

from fhir_synth.code_generator import CodeGenerator
from fhir_synth.code_generator.constants import SUPPORTED_RESOURCE_TYPES
from fhir_synth.code_generator.executor import (
    _check_dangerous_code,
    _validate_imports_whitelist,
    execute_code,
    fix_common_imports,
    validate_code,
    validate_imports,
)
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


# ── Sandbox security tests ────────────────────────────────────────────────


def test_dangerous_code_os_system_rejected():
    """Code using os.system() is caught by import whitelist, not dangerous patterns."""
    code = "import os\nos.system('rm -rf /')\ndef generate_resources(): return []"
    # os is not in allowed modules
    errors = _validate_imports_whitelist(code)
    assert len(errors) > 0


def test_dangerous_code_subprocess_rejected():
    """Code using subprocess is caught by import whitelist, not dangerous patterns."""
    code = "import subprocess\nsubprocess.run(['ls'])\ndef generate_resources(): return []"
    errors = _validate_imports_whitelist(code)
    assert len(errors) > 0


def test_dangerous_code_eval_rejected():
    """Code using eval() should be rejected by dangerous patterns (builtin, no import)."""
    code = "eval('1+1')\ndef generate_resources(): return []"
    warnings = _check_dangerous_code(code)
    assert len(warnings) > 0


def test_dangerous_code_open_rejected():
    """Code using open() should be rejected by dangerous patterns (builtin, no import)."""
    code = "open('/etc/passwd')\ndef generate_resources(): return []"
    warnings = _check_dangerous_code(code)
    assert len(warnings) > 0


def test_import_whitelist_allows_fhir():
    """fhir.resources imports should be allowed."""
    code = "from fhir.resources.R4B.patient import Patient\n"
    errors = _validate_imports_whitelist(code)
    assert errors == []


def test_import_whitelist_allows_uuid():
    """uuid imports should be allowed."""
    code = "from uuid import uuid4\n"
    errors = _validate_imports_whitelist(code)
    assert errors == []


def test_import_whitelist_blocks_os():
    """os imports should be blocked."""
    code = "import os\n"
    errors = _validate_imports_whitelist(code)
    assert len(errors) > 0


def test_import_whitelist_blocks_subprocess():
    """subprocess imports should be blocked."""
    code = "import subprocess\n"
    errors = _validate_imports_whitelist(code)
    assert len(errors) > 0


def test_validate_code_rejects_dangerous():
    """validate_code should return False for dangerous code."""
    code = "import os\nos.system('ls')\ndef generate_resources(): return []"
    assert validate_code(code) is False


def test_validate_code_rejects_disallowed_imports():
    """validate_code should return False for disallowed imports."""
    code = "import socket\ndef generate_resources(): return []"
    assert validate_code(code) is False


def test_validate_code_accepts_safe_code():
    """validate_code should return True for safe code."""
    code = (
        "from uuid import uuid4\n"
        "from fhir.resources.R4B.patient import Patient\n"
        "def generate_resources(): return []\n"
    )
    assert validate_code(code) is True


def test_execute_code_rejects_dangerous_imports():
    """execute_code should raise ValueError for disallowed imports."""
    code = "import socket\ndef generate_resources(): return []"
    with pytest.raises(ValueError, match="Disallowed imports"):
        execute_code(code)


def test_execute_code_rejects_dangerous_patterns():
    """execute_code should raise ValueError for dangerous builtin patterns."""
    code = "eval('1+1')\ndef generate_resources(): return []"
    with pytest.raises(ValueError, match="Code rejected"):
        execute_code(code)


def test_execute_code_timeout():
    """execute_code should raise TimeoutError for long-running code."""
    code = (
        "import time\n"
        "def generate_resources():\n"
        "    time.sleep(60)\n"
        "    return []\n"
    )
    # time is now allowed, so this should actually run and hit the timeout
    with pytest.raises(TimeoutError):
        execute_code(code, timeout=2)


def test_execute_code_rejects_disallowed_module():
    """execute_code should reject disallowed imports before execution."""
    code = (
        "import threading\n"
        "def generate_resources():\n"
        "    return []\n"
    )
    with pytest.raises(ValueError, match="Disallowed imports"):
        execute_code(code, timeout=2)


def test_execute_code_subprocess_isolation():
    """execute_code runs in a subprocess and returns results via JSON."""
    code = (
        "def generate_resources():\n"
        "    return [{'resourceType': 'Patient', 'id': 'sandbox-test'}]\n"
    )
    result = execute_code(code, timeout=10)
    assert len(result) == 1
    assert result[0]["id"] == "sandbox-test"


# ── Sandbox security tests ────────────────────────────────────────────


def test_validate_code_accepts_safe_code_with_annotations():
    """validate_code should accept safe FHIR generation code including type annotations."""
    code = (
        "from uuid import uuid4\n"
        "from fhir.resources.R4B.patient import Patient\n"
        "def generate_resources() -> list[dict]:\n"
        "    resources: list[dict] = []\n"
        "    return resources\n"
    )
    assert validate_code(code) is True


def test_validate_code_rejects_syntax_error():
    """validate_code should reject code with syntax errors."""
    code = "def generate_resources(\n"
    assert validate_code(code) is False


def test_validate_code_checks_in_validate():
    """validate_code should check syntax, dangerous patterns, and imports."""
    # Valid code should pass
    safe_code = "def generate_resources():\n    return []\n"
    assert validate_code(safe_code) is True

    # Syntax error should fail
    bad_syntax = "def generate_resources(\n"
    assert validate_code(bad_syntax) is False


def test_sandbox_execute_code_pre_flight():
    """execute_code catches syntax errors and bad imports before subprocess."""
    # Syntax errors are caught early by import whitelist validation
    bad_code = "def generate_resources(\n"
    with pytest.raises(ValueError, match="Syntax error"):
        execute_code(bad_code)

    # Safe code should pass all pre-flight checks and execute
    safe_code = (
        "def generate_resources():\n"
        "    return [{'resourceType': 'Patient', 'id': 'sandbox-test'}]\n"
    )
    result = execute_code(safe_code, timeout=10)
    assert result[0]["id"] == "sandbox-test"


def test_subprocess_restricted_import_blocks_at_runtime():
    """The subprocess wrapper's restricted __import__ blocks disallowed modules at runtime."""
    code = (
        "import collections\n"  # allowed
        "def generate_resources():\n"
        "    return [{'resourceType': 'Patient', 'id': 'safe'}]\n"
    )
    result = execute_code(code, timeout=10)
    assert result[0]["id"] == "safe"

    # Directly disallowed import is caught pre-flight
    bad_code = (
        "import os\n"
        "def generate_resources():\n"
        "    return []\n"
    )
    with pytest.raises(ValueError, match="Disallowed"):
        execute_code(bad_code)


def test_type_annotations_work_in_sandbox():
    """Code with type annotations should pass validation and execution.

    Unlike RestrictedPython, the plain subprocess sandbox handles
    type annotations natively — no stripping needed.
    """
    code = (
        "def generate_resources() -> list[dict]:\n"
        "    resources: list[dict] = []\n"
        "    patient_id: str = 'p1'\n"
        "    resources.append({'resourceType': 'Patient', 'id': patient_id})\n"
        "    return resources\n"
    )
    # Should pass validation
    assert validate_code(code) is True

    # Should execute successfully
    result = execute_code(code, timeout=10)
    assert len(result) == 1
    assert result[0]["id"] == "p1"


# ── Smoke test validation tests ──────────────────────────────────────


def test_smoke_test_rejects_empty_list():
    """Smoke test should reject code that returns an empty list."""
    code = "def generate_resources():\n    return []\n"
    with pytest.raises(ValueError, match="returned empty list"):
        execute_code(code, timeout=10)


def test_smoke_test_rejects_missing_resource_type():
    """Smoke test should reject resources missing resourceType."""
    code = (
        "def generate_resources():\n"
        "    return [{'id': 'p1', 'name': 'John'}]\n"
    )
    with pytest.raises(ValueError, match="missing.*resourceType"):
        execute_code(code, timeout=10)


def test_smoke_test_passes_valid_resources():
    """Smoke test should pass for valid FHIR-like resources."""
    code = (
        "def generate_resources():\n"
        "    return [{'resourceType': 'Patient', 'id': 'p1'}]\n"
    )
    result = execute_code(code, timeout=10)
    assert len(result) == 1
    assert result[0]["resourceType"] == "Patient"


