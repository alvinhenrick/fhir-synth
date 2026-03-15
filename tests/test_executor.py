"""Tests for the executor package — protocol, factory, and backends."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fhir_synth.code_generator.executor import (
    DifySandboxExecutor,
    E2BExecutor,
    ExecutionResult,
    Executor,
    ExecutorBackend,
    LocalSubprocessExecutor,
    get_executor,
)

# ── ExecutionResult ────────────────────────────────────────────────────────


def test_execution_result_defaults():
    r = ExecutionResult()
    assert r.stdout == ""
    assert r.stderr == ""
    assert r.artifacts == []


def test_execution_result_with_data():
    data = [{"resourceType": "Patient", "id": "p1"}]
    r = ExecutionResult(stdout="ok", stderr="", artifacts=data)
    assert r.artifacts == data


# ── Protocol compliance ───────────────────────────────────────────────────


def test_local_satisfies_protocol():
    assert isinstance(LocalSubprocessExecutor(), Executor)


def test_dify_satisfies_protocol():
    assert isinstance(DifySandboxExecutor(), Executor)


def test_e2b_satisfies_protocol():
    assert isinstance(E2BExecutor(), Executor)


# ── Factory ────────────────────────────────────────────────────────────────


def test_get_executor_local_string():
    ex = get_executor("local")
    assert isinstance(ex, LocalSubprocessExecutor)


def test_get_executor_dify_string():
    ex = get_executor("dify")
    assert isinstance(ex, DifySandboxExecutor)


def test_get_executor_e2b_string():
    ex = get_executor("e2b")
    assert isinstance(ex, E2BExecutor)


def test_get_executor_enum_value():
    ex = get_executor(ExecutorBackend.LOCAL)
    assert isinstance(ex, LocalSubprocessExecutor)


def test_get_executor_case_insensitive():
    ex = get_executor("Dify")
    assert isinstance(ex, DifySandboxExecutor)


def test_get_executor_unknown_raises():
    with pytest.raises(ValueError, match="Unknown executor backend"):
        get_executor("nonexistent")


def test_get_executor_dify_url_passed():
    ex = get_executor("dify", dify_url="http://sandbox:9999")
    assert isinstance(ex, DifySandboxExecutor)
    assert ex.base_url == "http://sandbox:9999"


def test_get_executor_e2b_api_key_passed():
    ex = get_executor("e2b", e2b_api_key="e2b_test_key")
    assert isinstance(ex, E2BExecutor)
    assert ex.api_key == "e2b_test_key"


# ── LocalSubprocessExecutor ───────────────────────────────────────────────


def test_local_subprocess_execute_simple_code():
    code = """
from fhir.resources.R4B import patient

def generate_resources():
    p = patient.Patient(id='p1', name=[{'given':['A'], 'family':'B'}])
    return [p.model_dump()]
"""
    executor = LocalSubprocessExecutor()
    result = executor.execute(code)
    assert len(result.artifacts) == 1
    assert result.artifacts[0]["id"] == "p1"
    assert result.artifacts[0]["resourceType"] == "Patient"
    assert result.stderr == "" or result.stderr is not None  # may have warnings


def test_local_subprocess_rejects_dangerous_code():
    code = "import os\nos.system('echo hacked')"
    executor = LocalSubprocessExecutor()
    with pytest.raises(ValueError, match="Disallowed imports"):
        executor.execute(code)


def test_local_subprocess_rejects_eval():
    code = "eval('1+1')"
    executor = LocalSubprocessExecutor()
    with pytest.raises(ValueError, match="Dangerous pattern"):
        executor.execute(code)


def test_local_subprocess_timeout():
    code = """
import time
def generate_resources():
    time.sleep(100)
    return []
"""
    executor = LocalSubprocessExecutor()
    with pytest.raises(TimeoutError):
        executor.execute(code, timeout=1)


# ── DifySandboxExecutor (mocked) ─────────────────────────────────────────


def test_dify_sandbox_missing_httpx_raises_import_error():
    executor = DifySandboxExecutor()
    executor._client = None
    with patch.dict("sys.modules", {"httpx": None}):
        with pytest.raises(ImportError, match="httpx"):
            executor._get_client()


def test_dify_sandbox_url_from_env_var():
    """DIFY_SANDBOX_URL env var is used when no base_url is passed."""
    import os

    with patch.dict(os.environ, {"DIFY_SANDBOX_URL": "http://sandbox.internal:8194"}):
        executor = DifySandboxExecutor()
        assert executor.base_url == "http://sandbox.internal:8194"


def test_dify_sandbox_explicit_url_overrides_env_var():
    """Explicit base_url takes priority over env var."""
    import os

    with patch.dict(os.environ, {"DIFY_SANDBOX_URL": "http://from-env:8194"}):
        executor = DifySandboxExecutor(base_url="http://explicit:8194")
        assert executor.base_url == "http://explicit:8194"


def test_dify_sandbox_default_url_when_nothing_set():
    """Falls back to localhost when no env var or arg."""
    import os

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("DIFY_SANDBOX_URL", None)
        executor = DifySandboxExecutor()
        assert executor.base_url == "http://localhost:8194"


def test_dify_sandbox_execute_with_mocked_httpx():
    import json

    resources = [{"resourceType": "Patient", "id": "dify-p1"}]

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": {
            "stdout": json.dumps(resources),
            "stderr": "",
            "error": "",
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    executor = DifySandboxExecutor()
    executor._client = mock_client

    code = "def generate_resources():\n    return [{'resourceType': 'Patient', 'id': 'dify-p1'}]"
    result = executor.execute(code)

    assert len(result.artifacts) == 1
    assert result.artifacts[0]["id"] == "dify-p1"
    mock_client.post.assert_called_once()


def test_dify_sandbox_error():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": {
            "stdout": "",
            "stderr": "",
            "error": "sandbox execution failed",
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    executor = DifySandboxExecutor()
    executor._client = mock_client

    code = "def generate_resources():\n    return []"
    with pytest.raises(RuntimeError, match="sandbox error"):
        executor.execute(code)


# ── E2BExecutor (mocked) ──────────────────────────────────────────────────


def test_e2b_missing_e2b_package_raises_import_error():
    executor = E2BExecutor(api_key="test-key")
    with patch.dict("sys.modules", {"e2b_code_interpreter": None}):
        with pytest.raises(ImportError, match="e2b-code-interpreter"):
            executor.execute("def generate_resources():\n    return []")


def test_e2b_missing_api_key_raises_value_error():
    import os

    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("E2B_API_KEY", None)
        executor = E2BExecutor(api_key="")
        # Mock the import so we get past it to the API key check
        mock_sandbox_cls = MagicMock()
        with patch.dict(
            "sys.modules", {"e2b_code_interpreter": MagicMock(Sandbox=mock_sandbox_cls)}
        ):
            with patch(
                "fhir_synth.code_generator.executor.e2b.Sandbox",
                create=True,
            ):
                with pytest.raises(ValueError, match="E2B_API_KEY"):
                    executor.execute("def generate_resources():\n    return []")


def test_e2b_api_key_from_env_var():
    import os

    with patch.dict(os.environ, {"E2B_API_KEY": "e2b_from_env"}):
        executor = E2BExecutor()
        assert executor.api_key == "e2b_from_env"


def test_e2b_explicit_api_key_overrides_env():
    import os

    with patch.dict(os.environ, {"E2B_API_KEY": "e2b_from_env"}):
        executor = E2BExecutor(api_key="e2b_explicit")
        assert executor.api_key == "e2b_explicit"


# ── CodeGenerator integration ─────────────────────────────────────────────


def test_code_generator_accepts_custom_executor():
    """CodeGenerator can be initialized with any executor backend."""
    from fhir_synth.code_generator import CodeGenerator
    from fhir_synth.llm import MockLLMProvider

    llm = MockLLMProvider()
    executor = LocalSubprocessExecutor()
    cg = CodeGenerator(llm, executor=executor)
    assert cg.executor is executor


def test_code_generator_defaults_to_local():
    from fhir_synth.code_generator import CodeGenerator
    from fhir_synth.llm import MockLLMProvider

    llm = MockLLMProvider()
    cg = CodeGenerator(llm)
    assert isinstance(cg.executor, LocalSubprocessExecutor)
