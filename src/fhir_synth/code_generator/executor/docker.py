"""Docker executor — powered by smolagents.

Runs LLM-generated code in a Docker container using smolagents'
`DockerExecutor <https://huggingface.co/docs/smolagents/tutorials/secure_code_execution#docker-setup>`_.
Provides full OS-level isolation via Docker.

smolagents automatically build the Docker image (install dependencies),
create a container running a Jupyter Kernel Gateway, and communicate
with it over a WebSocket.  You do **not** need to manually create or start
containers — just have the Docker daemon running.

Requires the ``docker`` Python package::

    pip install "fhir-synth[docker]"

A local Docker daemon must be running (``docker info`` should succeed).
"""

from __future__ import annotations

import json
import logging
import socket
from typing import Any

from fhir_synth.code_generator.executor.base import (
    ExecutionResult,
    get_execution_packages,
    get_smolagents_logger,
)
from fhir_synth.code_generator.executor.validation import build_runner_script

logger = logging.getLogger(__name__)


class DockerSandboxExecutor:
    """Execute generated code in a Docker container via smolagents.

    smolagents' ``DockerExecutor`` handles the full container lifecycle:

    1. **Builds** a Docker image with the required Python packages.
    2. **Creates & starts** a container running Jupyter Kernel Gateway.
    3. **Executes** code cells over a WebSocket connection.
    4. **Cleans up** the container on :meth:`cleanup`.

    The container is created once and **reused** for all subsequent
    ``execute()`` calls (including retries).  Stale containers from
    previous runs are automatically cleaned up before starting.

    A free port is selected automatically by default so multiple
    instances can run in parallel without conflicts.

    All parameters are optional — sensible defaults match smolagents.

    Args:
        host: Host address to bind the Jupyter gateway.
        port: Port for the Jupyter kernel gateway.  ``0`` (default)
            means *auto-select a free port*.
        image_name: Docker image name (built automatically if missing).
        build_new_image: Rebuild the image even if it already exists.
            Defaults to ``False`` — the image is built only on first use.
        timeout: Execution timeout in seconds.
        container_run_kwargs: Extra kwargs passed to ``docker container run``.
        dockerfile_content: Custom Dockerfile content (``None`` = smolagents default).
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        image_name: str = "fhir-synth-sandbox",
        build_new_image: bool = False,
        timeout: int = 120,
        container_run_kwargs: dict[str, Any] | None = None,
        dockerfile_content: str | None = None,
    ) -> None:
        self.host = host
        self.port = port if port != 0 else _find_free_port(host)
        self.image_name = image_name
        self.build_new_image = build_new_image
        self.timeout = timeout
        self.container_run_kwargs = container_run_kwargs
        self.dockerfile_content = dockerfile_content
        self._executor: Any = None

    # ── Public API ─────────────────────────────────────────────────────

    def execute(self, code: str, timeout: int = 0) -> ExecutionResult:
        """Run *code* in a Docker container via smolagents.

        The container is created lazily on the first call and reused for
        subsequent calls.  Code execution errors do **not** tear down the
        container — only :meth:`cleanup` does that.

        Args:
            code: Python source defining ``generate_resources() -> list[dict]``.
            timeout: Maximum wall-clock seconds (0 = use default).

        Returns:
            :class:`ExecutionResult` with parsed FHIR resource dicts.

        Raises:
            RuntimeError: Execution or container error.
        """

        timeout = timeout or self.timeout

        # smolagents installs packages during DockerExecutor init via
        # install_packages(), so no pip_install_packages needed here.
        script = build_runner_script(code)

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
        """Lazy-init the smolagents DockerExecutor.

        smolagents will automatically build the Docker image and start a
        container with a Jupyter Kernel Gateway — no manual Docker setup
        is required beyond having the daemon running.

        Before creating a new executor, any stale containers from previous
        runs that occupy the same port are removed.
        """
        if self._executor is not None:
            return self._executor

        try:
            from smolagents import DockerExecutor
        except ImportError:
            raise ImportError(
                "DockerSandboxExecutor requires the 'docker' package. "
                'Install it with: pip install "smolagents[docker]"'
            )

        # Remove leftover containers from previous runs to free the port.
        self._cleanup_stale_containers()

        packages = get_execution_packages()

        kwargs: dict[str, Any] = {
            "additional_imports": [
                p.split(">")[0].split("<")[0].split("=")[0].strip() for p in packages
            ],
            "logger": get_smolagents_logger(),
            "host": self.host,
            "port": self.port,
            "image_name": self.image_name,
            "build_new_image": self.build_new_image,
        }
        if self.container_run_kwargs is not None:
            kwargs["container_run_kwargs"] = self.container_run_kwargs
        if self.dockerfile_content is not None:
            kwargs["dockerfile_content"] = self.dockerfile_content

        self._executor = DockerExecutor(**kwargs)
        return self._executor

    def _cleanup_stale_containers(self) -> None:
        """Remove any leftover containers using our image that hold the port.

        This prevents ``Bind for 127.0.0.1:8888 failed: port is already
        allocated`` errors when a previous run crashed without cleanup.
        """
        try:
            import docker as docker_sdk  # type: ignore[import-untyped]

            client = docker_sdk.from_env()
            # Find containers (running or stopped) using our image.
            containers = client.containers.list(
                all=True,
                filters={"ancestor": self.image_name},
            )
            for container in containers:
                try:
                    container.remove(force=True)
                    logger.debug("Removed stale container %s", container.short_id)
                except Exception:
                    pass
        except Exception:
            # If Docker SDK isn't available or the daemon is down, the
            # DockerExecutor init will raise a proper error anyway.
            pass

    def cleanup(self) -> None:
        """Clean up Docker resources (stop & remove the container)."""
        if self._executor is not None:
            try:
                self._executor.cleanup()
            except Exception:
                logger.debug("Error during Docker executor cleanup", exc_info=True)
            self._executor = None


def _find_free_port(host: str = "127.0.0.1") -> int:
    """Ask the OS for an available TCP port on *host*."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])
