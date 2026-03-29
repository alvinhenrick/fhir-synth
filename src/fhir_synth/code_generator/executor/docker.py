"""Docker executor — powered by smolagents.

Runs LLM-generated code in a Docker container using smolagents'
`DockerExecutor <https://huggingface.co/docs/smolagents/tutorials/secure_code_execution>`_.
Provides full OS-level isolation via Docker.

Requires the ``docker`` Python package::

    pip install "fhir-synth[docker]"

A local Docker daemon must be running.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fhir_synth.code_generator.executor.base import ExecutionResult, get_execution_packages
from fhir_synth.code_generator.executor.validation import build_runner_script

logger = logging.getLogger(__name__)


class DockerSandboxExecutor:
    """Execute generated code in a Docker container via smolagents.

    Uses smolagents' ``DockerExecutor`` which runs a Jupyter kernel
    inside a Docker container and communicates via websocket.

    Args:
        host: Docker host address.
        port: Port for the Jupyter kernel gateway.
        image_name: Docker image name to use.
        timeout: Execution timeout in seconds.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8888,
        image_name: str = "fhir-synth-sandbox",
        timeout: int = 120,
    ) -> None:
        self.host = host
        self.port = port
        self.image_name = image_name
        self.timeout = timeout
        self._executor: Any = None

    # ── Public API ─────────────────────────────────────────────────────

    def execute(self, code: str, timeout: int = 0) -> ExecutionResult:
        """Run *code* in a Docker container via smolagents.

        Args:
            code: Python source defining ``generate_resources() -> list[dict]``.
            timeout: Maximum wall-clock seconds (0 = use default).

        Returns:
            :class:`ExecutionResult` with parsed FHIR resource dicts.

        Raises:
            RuntimeError: Execution or container error.
        """

        timeout = timeout or self.timeout

        # ── Build the runner script ───────────────────────────────────
        packages = get_execution_packages()
        script = build_runner_script(code, pip_install_packages=packages)

        # ── Execute in Docker via smolagents ──────────────────────────
        executor = self._get_executor()

        logger.info("Running code in Docker container via smolagents")

        try:
            output = executor.run_code_raise_errors(script)
        except Exception as exc:
            raise RuntimeError(f"Docker execution error: {exc}") from exc

        stdout_text = output.logs.strip() if output.logs else ""

        if not stdout_text:
            raise RuntimeError("Docker sandbox produced no output")

        data = json.loads(stdout_text)
        if isinstance(data, dict) and "__error__" in data:
            raise ValueError(data["__error__"])

        if not isinstance(data, list):
            raise RuntimeError(
                f"Expected list from generate_resources(), got {type(data).__name__}"
            )

        return ExecutionResult(
            stdout=stdout_text,
            stderr="",
            artifacts=data,
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_executor(self) -> Any:
        """Lazy-init the smolagents DockerExecutor."""
        if self._executor is not None:
            return self._executor

        try:
            from smolagents import DockerExecutor
        except ImportError:
            raise ImportError(
                "DockerSandboxExecutor requires the 'docker' package. "
                'Install it with: pip install "smolagents[docker]"'
            )

        packages = get_execution_packages()

        self._executor = DockerExecutor(
            additional_imports=[
                p.split(">")[0].split("<")[0].split("=")[0].strip() for p in packages
            ],
            logger=logger,
            host=self.host,
            port=self.port,
            image_name=self.image_name,
        )
        return self._executor

    def cleanup(self) -> None:
        """Clean up Docker resources."""
        if self._executor is not None:
            self._executor.cleanup()
            self._executor = None
