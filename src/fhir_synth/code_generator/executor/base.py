"""Executor protocol and result model.

All executor backends implement the: class:`Executor` protocol so that
calling code is backend-agnostic.
"""

import enum
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class ExecutorBackend(enum.StrEnum):
    """Supported executor backends."""

    LOCAL = "local"
    DOCKER = "docker"
    DIFY = "dify"


@dataclass
class ExecutionResult:
    """Uniform result returned by every executor backend.

    Attributes:
        stdout: Raw standard output from the execution.
        stderr: Raw standard error from the execution.
        artifacts: Parsed list of FHIR resource dicts (the real payload).
    """

    stdout: str = ""
    stderr: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class Executor(Protocol):
    """Protocol that every executor backend must satisfy."""

    def execute(self, code: str, timeout: int = 30) -> ExecutionResult:
        """Execute *code* and return an :class:`ExecutionResult`.

        Args:
            code: Python source that defines ``generate_resources() -> list[dict]``.
            timeout: Maximum wall-clock seconds before the process is killed.

        Returns:
            An :class:`ExecutionResult` with stdout, stderr, and parsed artifacts.

        Raises:
            ValueError: If the code is rejected by pre-flight safety checks.
            TimeoutError: If execution exceeds *timeout* seconds.
            RuntimeError: If the code exits with a non-zero status.
        """
        ...


def get_executor(
    backend: str | ExecutorBackend = ExecutorBackend.LOCAL,
    *,
    docker_image: str | None = None,
    dify_url: str | None = None,
    dify_api_key: str | None = None,
) -> Executor:
    """Factory that returns a concrete executor for the requested backend.

    Args:
        backend: One of ``"local"``, ``"docker"``, ``"dify"`` (or an:             class:`ExecutorBackend` enum member).
        docker_image: Docker image override (only used when *backend* is
            ``"docker"``).
        dify_url: Base URL for the dify-sandbox service (only used when
            *backend* is ``"dify"``).
        dify_api_key: API key for dify-sandbox authentication.

    Returns:
        An object satisfying the: class:`Executor` protocol.

    Raises:
        ValueError: If *backend* is not recognised.
        ImportError: If the backend requires an optional dependency, that is
            not installed.
    """
    if isinstance(backend, str):
        try:
            backend = ExecutorBackend(backend.lower())
        except ValueError:
            valid = ", ".join(b.value for b in ExecutorBackend)
            raise ValueError(f"Unknown executor backend {backend!r}. Choose from: {valid}")

    if backend is ExecutorBackend.LOCAL:
        from fhir_synth.code_generator.executor.local import LocalSubprocessExecutor

        return LocalSubprocessExecutor()

    if backend is ExecutorBackend.DOCKER:
        from fhir_synth.code_generator.executor.docker import DockerExecutor

        kwargs: dict[str, Any] = {}
        if docker_image:
            kwargs["image"] = docker_image
        return DockerExecutor(**kwargs)

    if backend is ExecutorBackend.DIFY:
        from fhir_synth.code_generator.executor.dify import DifySandboxExecutor

        kwargs = {}
        if dify_url:
            kwargs["base_url"] = dify_url
        if dify_api_key:
            kwargs["api_key"] = dify_api_key
        return DifySandboxExecutor(**kwargs)

    # Should be unreachable
    raise ValueError(f"Unhandled backend: {backend}")
