"""Tests for the executor package — protocol, factory, and backends."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fhir_synth.code_generator.executor import (
    DifySandboxExecutor,
    DockerExecutor,
    ExecutionResult,
    Executor,
    ExecutorBackend,
    LocalSubprocessExecutor,
    execute_code,
    get_executor,
)

# ── ExecutionResult ────────────────────────────────────────────────────────


class TestExecutionResult:
    def test_defaults(self):
        r = ExecutionResult()
        assert r.stdout == ""
        assert r.stderr == ""
        assert r.artifacts == []

    def test_with_data(self):
        data = [{"resourceType": "Patient", "id": "p1"}]
        r = ExecutionResult(stdout="ok", stderr="", artifacts=data)
        assert r.artifacts == data


# ── Protocol compliance ───────────────────────────────────────────────────


class TestExecutorProtocol:
    def test_local_satisfies_protocol(self):
        assert isinstance(LocalSubprocessExecutor(), Executor)

    def test_docker_satisfies_protocol(self):
        assert isinstance(DockerExecutor(), Executor)

    def test_dify_satisfies_protocol(self):
        assert isinstance(DifySandboxExecutor(), Executor)


# ── Factory ────────────────────────────────────────────────────────────────


class TestGetExecutor:
    def test_local_string(self):
        ex = get_executor("local")
        assert isinstance(ex, LocalSubprocessExecutor)

    def test_docker_string(self):
        ex = get_executor("docker")
        assert isinstance(ex, DockerExecutor)

    def test_dify_string(self):
        ex = get_executor("dify")
        assert isinstance(ex, DifySandboxExecutor)

    def test_enum_value(self):
        ex = get_executor(ExecutorBackend.LOCAL)
        assert isinstance(ex, LocalSubprocessExecutor)

    def test_case_insensitive(self):
        ex = get_executor("Docker")
        assert isinstance(ex, DockerExecutor)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown executor backend"):
            get_executor("nonexistent")

    def test_docker_image_passed(self):
        ex = get_executor("docker", docker_image="my-image:latest")
        assert isinstance(ex, DockerExecutor)
        assert ex.image == "my-image:latest"

    def test_dify_url_passed(self):
        ex = get_executor("dify", dify_url="http://sandbox:9999")
        assert isinstance(ex, DifySandboxExecutor)
        assert ex.base_url == "http://sandbox:9999"


# ── LocalSubprocessExecutor ───────────────────────────────────────────────


class TestLocalSubprocessExecutor:
    def test_execute_simple_code(self):
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

    def test_rejects_dangerous_code(self):
        code = "import os\nos.system('echo hacked')"
        executor = LocalSubprocessExecutor()
        with pytest.raises(ValueError, match="Disallowed imports"):
            executor.execute(code)

    def test_rejects_eval(self):
        code = "eval('1+1')"
        executor = LocalSubprocessExecutor()
        with pytest.raises(ValueError, match="Dangerous pattern"):
            executor.execute(code)

    def test_timeout(self):
        code = """
import time
def generate_resources():
    time.sleep(100)
    return []
"""
        executor = LocalSubprocessExecutor()
        with pytest.raises(TimeoutError):
            executor.execute(code, timeout=1)


# ── Backward compatibility ────────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_execute_code_function(self):
        """The old execute_code() function should still work."""
        code = """
def generate_resources():
    return [{'resourceType': 'Patient', 'id': 'compat-test'}]
"""
        result = execute_code(code)
        assert isinstance(result, list)
        assert result[0]["id"] == "compat-test"

    def test_old_private_names_importable(self):
        """Old private names _check_dangerous_code etc. are still importable."""
        from fhir_synth.code_generator.executor import (
            _check_dangerous_code,
            _validate_imports_whitelist,
        )

        assert callable(_check_dangerous_code)
        assert callable(_validate_imports_whitelist)


# ── DockerExecutor (mocked) ──────────────────────────────────────────────


class TestDockerExecutor:
    def test_missing_docker_package_raises_import_error(self):
        executor = DockerExecutor()
        executor._client = None  # reset
        with patch.dict("sys.modules", {"docker": None}):
            with pytest.raises(ImportError, match="docker"):
                executor._get_client()

    def test_execute_with_mocked_docker(self):
        import json

        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        resources = [{"resourceType": "Patient", "id": "docker-p1"}]
        mock_container.logs.side_effect = [
            json.dumps(resources).encode(),  # stdout
            b"",  # stderr
        ]

        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container

        executor = DockerExecutor()
        executor._client = mock_client

        code = """
def generate_resources():
    return [{'resourceType': 'Patient', 'id': 'docker-p1'}]
"""
        result = executor.execute(code)
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["id"] == "docker-p1"
        mock_client.containers.run.assert_called_once()
        mock_container.remove.assert_called_once_with(force=True)

    def test_docker_non_zero_exit(self):
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 1}
        mock_container.logs.side_effect = [
            b"",  # stdout
            b"SyntaxError: invalid syntax",  # stderr
        ]

        mock_client = MagicMock()
        mock_client.containers.run.return_value = mock_container

        executor = DockerExecutor()
        executor._client = mock_client

        code = "def generate_resources():\n    return []"
        with pytest.raises(RuntimeError, match="exited with code 1"):
            executor.execute(code)


# ── DifySandboxExecutor (mocked) ─────────────────────────────────────────


class TestDifySandboxExecutor:
    def test_missing_httpx_raises_import_error(self):
        executor = DifySandboxExecutor()
        executor._client = None
        with patch.dict("sys.modules", {"httpx": None}):
            with pytest.raises(ImportError, match="httpx"):
                executor._get_client()

    def test_execute_with_mocked_httpx(self):
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

        executor = DifySandboxExecutor(api_key="test-key")
        executor._client = mock_client

        code = (
            "def generate_resources():\n    return [{'resourceType': 'Patient', 'id': 'dify-p1'}]"
        )
        result = executor.execute(code)

        assert len(result.artifacts) == 1
        assert result.artifacts[0]["id"] == "dify-p1"
        mock_client.post.assert_called_once()

    def test_dify_sandbox_error(self):
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


# ── CodeGenerator integration ─────────────────────────────────────────────


class TestCodeGeneratorExecutorIntegration:
    def test_code_generator_accepts_custom_executor(self):
        """CodeGenerator can be initialized with any executor backend."""
        from fhir_synth.code_generator import CodeGenerator
        from fhir_synth.llm import MockLLMProvider

        llm = MockLLMProvider()
        executor = LocalSubprocessExecutor()
        cg = CodeGenerator(llm, executor=executor)
        assert cg.executor is executor

    def test_code_generator_defaults_to_local(self):
        from fhir_synth.code_generator import CodeGenerator
        from fhir_synth.llm import MockLLMProvider

        llm = MockLLMProvider()
        cg = CodeGenerator(llm)
        assert isinstance(cg.executor, LocalSubprocessExecutor)
