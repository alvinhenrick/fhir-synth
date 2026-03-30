"""Tests for the executor package — protocol, factory, and backends (smolagents)."""

from __future__ import annotations

import pytest

from fhir_synth.code_generator.executor import (
    BlaxelExecutor,
    DockerSandboxExecutor,
    E2BExecutor,
    ExecutionResult,
    Executor,
    ExecutorBackend,
    LocalSmolagentsExecutor,
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
    assert isinstance(LocalSmolagentsExecutor(), Executor)


def test_docker_satisfies_protocol():
    assert isinstance(DockerSandboxExecutor(), Executor)


def test_e2b_satisfies_protocol():
    assert isinstance(E2BExecutor(), Executor)


# ── Factory ────────────────────────────────────────────────────────────────


def test_get_executor_local_string():
    ex = get_executor("local")
    assert isinstance(ex, LocalSmolagentsExecutor)


def test_get_executor_docker_string():
    ex = get_executor("docker")
    assert isinstance(ex, DockerSandboxExecutor)


def test_get_executor_e2b_string():
    ex = get_executor("e2b")
    assert isinstance(ex, E2BExecutor)


def test_get_executor_enum_value():
    ex = get_executor(ExecutorBackend.LOCAL)
    assert isinstance(ex, LocalSmolagentsExecutor)


def test_get_executor_case_insensitive():
    ex = get_executor("Docker")
    assert isinstance(ex, DockerSandboxExecutor)


def test_get_executor_unknown_raises():
    with pytest.raises(ValueError, match="Unknown executor backend"):
        get_executor("nonexistent")


# ── LocalSmolagentsExecutor ──────────────────────────────────────────────
# NOTE: Execution tests live in test_code_generator.py. Here we only test
# that smolagents block disallowed code at runtime.


def test_local_smolagents_rejects_disallowed_import():
    executor = LocalSmolagentsExecutor()
    with pytest.raises(RuntimeError, match="not allowed|not among"):
        executor.execute("import os\ndef generate_resources(): return []")


# ── DockerSandboxExecutor (unit tests — no Docker daemon needed) ──────────


def test_docker_sandbox_default_config():
    ex = DockerSandboxExecutor()
    assert ex.host == "127.0.0.1"
    assert ex.port > 0  # dynamically assigned free port
    assert ex.image_name == "fhir-synth-sandbox"
    assert ex.build_new_image is False
    assert ex.timeout == 120
    assert ex.container_run_kwargs is None
    assert ex.dockerfile_content is None


def test_docker_sandbox_custom_config():
    ex = DockerSandboxExecutor(
        host="192.168.1.1",
        port=9999,
        image_name="custom-img",
        build_new_image=True,
        container_run_kwargs={"network_mode": "host"},
        dockerfile_content="FROM python:3.12-slim",
    )
    assert ex.host == "192.168.1.1"
    assert ex.port == 9999
    assert ex.image_name == "custom-img"
    assert ex.build_new_image is True
    assert ex.container_run_kwargs == {"network_mode": "host"}
    assert ex.dockerfile_content == "FROM python:3.12-slim"


def test_docker_sandbox_dynamic_port_avoids_conflicts():
    """Two instances get different ports — no conflicts."""
    ex1 = DockerSandboxExecutor()
    ex2 = DockerSandboxExecutor()
    assert ex1.port != ex2.port


# ── E2BExecutor (mocked) ──────────────────────────────────────────────────


def test_e2b_api_key_from_env_var(mocker):
    mocker.patch.dict("os.environ", {"E2B_API_KEY": "e2b_from_env"})
    executor = E2BExecutor()
    assert executor.api_key == "e2b_from_env"


def test_e2b_explicit_api_key_overrides_env(mocker):
    mocker.patch.dict("os.environ", {"E2B_API_KEY": "e2b_from_env"})
    executor = E2BExecutor(api_key="e2b_explicit")
    assert executor.api_key == "e2b_explicit"


# ── BlaxelExecutor (unit tests) ───────────────────────────────────────────


def test_blaxel_satisfies_protocol():
    assert isinstance(BlaxelExecutor(), Executor)


def test_get_executor_blaxel_string():
    ex = get_executor("blaxel")
    assert isinstance(ex, BlaxelExecutor)


def test_blaxel_default_config():
    ex = BlaxelExecutor()
    assert ex.sandbox_name is None
    assert ex.image == "blaxel/jupyter-notebook"
    assert ex.memory == 4096


def test_blaxel_custom_config():
    ex = BlaxelExecutor(sandbox_name="my-sandbox", image="custom-img", memory=8192)
    assert ex.sandbox_name == "my-sandbox"
    assert ex.image == "custom-img"
    assert ex.memory == 8192


# ── CodeGenerator integration ─────────────────────────────────────────────


def test_code_generator_accepts_custom_executor():
    """CodeGenerator can be initialized with any executor backend."""
    from fhir_synth.code_generator import CodeGenerator
    from fhir_synth.llm import MockLLMProvider

    llm = MockLLMProvider()
    executor = LocalSmolagentsExecutor()
    cg = CodeGenerator(llm, executor=executor)
    assert cg.executor is executor


def test_code_generator_defaults_to_local_smolagents():
    from fhir_synth.code_generator import CodeGenerator
    from fhir_synth.llm import MockLLMProvider

    llm = MockLLMProvider()
    cg = CodeGenerator(llm)
    assert isinstance(cg.executor, LocalSmolagentsExecutor)
