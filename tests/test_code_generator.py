"""Tests for code generation."""

import pytest

from fhir_synth.code_generator import CodeGenerator
from fhir_synth.code_generator.executor import (
    LocalSubprocessExecutor,
    check_dangerous_code,
    fix_common_imports,
    validate_code,
    validate_imports,
    validate_imports_whitelist,
)
from fhir_synth.llm import MockLLMProvider

_executor = LocalSubprocessExecutor()


# ── CodeGenerator ─────────────────────────────────────────────────────────


def test_apply_metadata_to_resources():
    """Metadata fields are applied to every resource."""
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
    code = (
        "from fhir.resources.R4B import patient\n"
        "def generate_resources():\n"
        "    p = patient.Patient(id='p1', name=[{'given':['A'], 'family':'B'}])\n"
        "    return [p.model_dump()]\n"
    )
    llm = MockLLMProvider(response=code)
    code_gen = CodeGenerator(llm)
    generated_code = code_gen.generate_code_from_prompt("test")
    resources = code_gen.execute_generated_code(generated_code)
    assert len(resources) == 1
    assert resources[0]["id"] == "p1"


def test_self_healing_retry_fixes_broken_code():
    """First code fails, LLM is asked to fix it, retry succeeds."""
    bad_code = "def generate_resources():\n    return 1/0"
    good_code = "def generate_resources():\n    return [{'resourceType': 'Patient', 'id': 'fixed'}]"

    class _HealingMock(MockLLMProvider):
        def __init__(self) -> None:
            super().__init__()
            self._call_count = 0

        def generate_text(self, prompt, system=None, json_schema=None):  # type: ignore[override]
            self._call_count += 1
            return bad_code if self._call_count <= 1 else good_code

    code_gen = CodeGenerator(_HealingMock(), max_retries=2)
    generated = code_gen.generate_code_from_prompt("test")
    resources = code_gen.execute_generated_code(generated)
    assert len(resources) == 1
    assert resources[0]["id"] == "fixed"


def test_supported_resource_types_has_no_concatenation_bugs():
    from fhir_synth.fhir_spec import resource_names

    for rt in resource_names():
        assert rt[0].isupper(), f"{rt} does not start with uppercase"
        assert " " not in rt, f"{rt} contains a space"
        assert len(rt) < 50, f"{rt} looks like a concatenation bug"


# ── fix_common_imports ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code, expected_in, not_expected_in",
    [
        # Wrong module → rewritten
        (
            "from fhir.resources.R4B.timingrepeat import TimingRepeat\n",
            ["from fhir.resources.R4B.timing import TimingRepeat"],
            ["timingrepeat"],
        ),
        # Correct import → unchanged
        (
            "from fhir.resources.R4B.patient import Patient\n",
            ["from fhir.resources.R4B.patient import Patient"],
            [],
        ),
        # DosageDoseAndRate wrong module → fixed
        (
            "from fhir.resources.R4B.dosagedoseandrate import DosageDoseAndRate\n",
            ["from fhir.resources.R4B.dosage import DosageDoseAndRate"],
            [],
        ),
    ],
)
def test_fix_common_imports_rewrite(code, expected_in, not_expected_in):
    fixed = fix_common_imports(code)
    for fragment in expected_in:
        assert fragment in fixed
    for fragment in not_expected_in:
        assert fragment not in fixed


def test_fix_common_imports_handles_multiple_classes():
    code = "from fhir.resources.R4B.timing import Timing, TimingRepeat\n"
    fixed = fix_common_imports(code)
    assert "Timing" in fixed
    assert "TimingRepeat" in fixed
    assert "from fhir.resources.R4B.timing import" in fixed


def test_fix_common_imports_splits_classes_to_different_modules():
    code = "from fhir.resources.R4B.wrong import Patient, Coding\n"
    fixed = fix_common_imports(code)
    assert "from fhir.resources.R4B.patient import Patient" in fixed
    assert "from fhir.resources.R4B.coding import Coding" in fixed


def test_fix_common_imports_preserves_non_fhir_imports():
    code = "from uuid import uuid4\nimport random\nfrom fhir.resources.R4B.patient import Patient\n"
    fixed = fix_common_imports(code)
    assert "from uuid import uuid4" in fixed
    assert "import random" in fixed


def test_fix_common_imports_handles_unknown_class_gracefully():
    code = "from fhir.resources.R4B.patient import Patient, SomethingWeird\n"
    fixed = fix_common_imports(code)
    assert "Patient" in fixed
    assert "SomethingWeird" in fixed


def test_validate_imports_detects_bad_module():
    code = "from fhir.resources.R4B.timingrepeat import TimingRepeat\n"
    errors = validate_imports(code)
    assert len(errors) >= 1
    assert any("timingrepeat" in e for e in errors)
    assert any("timing" in e for e in errors)


# ── Import whitelist ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code",
    [
        "from fhir.resources.R4B.patient import Patient\n",
        "from uuid import uuid4\n",
        "import collections\n",
        "from datetime import datetime\n",
    ],
)
def test_import_whitelist_allows(code):
    assert validate_imports_whitelist(code) == []


@pytest.mark.parametrize(
    "code",
    [
        "import os\n",
        "import subprocess\n",
        "import socket\n",
        "import threading\n",
    ],
)
def test_import_whitelist_blocks(code):
    assert len(validate_imports_whitelist(code)) > 0


# ── Dangerous code detection ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "code",
    [
        "import os\nos.system('rm -rf /')\ndef generate_resources(): return []",
        "import subprocess\nsubprocess.run(['ls'])\ndef generate_resources(): return []",
    ],
)
def test_dangerous_import_rejected_by_whitelist(code):
    assert len(validate_imports_whitelist(code)) > 0


@pytest.mark.parametrize(
    "code",
    [
        "eval('1+1')\ndef generate_resources(): return []",
        "open('/etc/passwd')\ndef generate_resources(): return []",
    ],
)
def test_dangerous_builtin_rejected(code):
    assert len(check_dangerous_code(code)) > 0


# ── validate_code ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code",
    [
        "from uuid import uuid4\nfrom fhir.resources.R4B.patient import Patient\ndef generate_resources(): return []\n",
        "def generate_resources():\n    return []\n",
        (
            "from uuid import uuid4\n"
            "from fhir.resources.R4B.patient import Patient\n"
            "def generate_resources() -> list[dict]:\n"
            "    resources: list[dict] = []\n"
            "    return resources\n"
        ),
    ],
)
def test_validate_code_accepts_safe(code):
    assert validate_code(code) is True


@pytest.mark.parametrize(
    "code",
    [
        "import os\nos.system('ls')\ndef generate_resources(): return []",
        "import socket\ndef generate_resources(): return []",
        "def generate_resources(\n",
    ],
)
def test_validate_code_rejects_unsafe(code):
    assert validate_code(code) is False


# ── Executor: pre-flight rejection ───────────────────────────────────────


@pytest.mark.parametrize(
    "code, match",
    [
        ("import socket\ndef generate_resources(): return []", "Disallowed imports"),
        ("import threading\ndef generate_resources():\n    return []\n", "Disallowed imports"),
        ("eval('1+1')\ndef generate_resources(): return []", "Code rejected"),
        ("import os\ndef generate_resources():\n    return []\n", "Disallowed"),
        ("def generate_resources(\n", "Syntax error"),
    ],
)
def test_executor_rejects_bad_code(code, match):
    with pytest.raises(ValueError, match=match):
        _executor.execute(code)


def test_executor_timeout():
    code = "import time\ndef generate_resources():\n    time.sleep(60)\n    return []\n"
    with pytest.raises(TimeoutError):
        _executor.execute(code, timeout=2)


# ── Executor: successful execution ───────────────────────────────────────


@pytest.mark.parametrize(
    "code, expected_id",
    [
        (
            "def generate_resources():\n"
            "    return [{'resourceType': 'Patient', 'id': 'sandbox-test'}]\n",
            "sandbox-test",
        ),
        (
            "import collections\n"
            "def generate_resources():\n"
            "    return [{'resourceType': 'Patient', 'id': 'safe'}]\n",
            "safe",
        ),
        (
            "def generate_resources() -> list[dict]:\n"
            "    resources: list[dict] = []\n"
            "    patient_id: str = 'p1'\n"
            "    resources.append({'resourceType': 'Patient', 'id': patient_id})\n"
            "    return resources\n",
            "p1",
        ),
    ],
)
def test_executor_runs_valid_code(code, expected_id):
    result = _executor.execute(code, timeout=10)
    assert len(result.artifacts) >= 1
    assert result.artifacts[0]["id"] == expected_id


# ── Smoke test validation ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "code, match",
    [
        ("def generate_resources():\n    return []\n", "returned empty list"),
        (
            "def generate_resources():\n    return [{'id': 'p1', 'name': 'John'}]\n",
            "missing.*resourceType",
        ),
    ],
)
def test_smoke_test_rejects_invalid_output(code, match):
    with pytest.raises(ValueError, match=match):
        _executor.execute(code, timeout=10)


def test_smoke_test_passes_valid_resources():
    code = "def generate_resources():\n    return [{'resourceType': 'Patient', 'id': 'p1'}]\n"
    result = _executor.execute(code, timeout=10)
    assert len(result.artifacts) == 1
    assert result.artifacts[0]["resourceType"] == "Patient"


def test_fix_naive_date_times_wraps_isoformat():
    from fhir_synth.code_generator.executor.validation import fix_naive_date_times

    code = '''
from datetime import datetime, timedelta, date

def generate_resources():
    start = datetime(2025, 3, 8, 10, 30)
    end = start + timedelta(hours=1)
    onset = date(2025, 3, 8)
    return [
        {"start": start.isoformat(), "end": end.isoformat()},
        {"onset": onset.isoformat()},
    ]
'''
    fixed = fix_naive_date_times(code)
    glb: dict[str, object] = {}
    exec(compile(fixed, "<test>", "exec"), glb)
    result = glb["generate_resources"]()

    assert result[0]["start"].endswith("+00:00")
    assert result[0]["end"].endswith("+00:00")
    assert result[1]["onset"] == "2025-03-08"
