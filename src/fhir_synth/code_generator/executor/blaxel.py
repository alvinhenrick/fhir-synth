"""Blaxel executor — powered by smolagents.

Runs LLM-generated code in a `Blaxel <https://blaxel.ai>`_ cloud sandbox
via smolagents' ``BlaxelExecutor``.  Blaxel provides managed serverless
sandboxes with Jupyter notebooks.

Requires the ``blaxel-core`` package::

    pip install "fhir-synth[blaxel]"
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fhir_synth.code_generator.executor.base import ExecutionResult, get_execution_packages
from fhir_synth.code_generator.executor.validation import build_runner_script

logger = logging.getLogger(__name__)


class BlaxelExecutor:
    """Execute generated code in a Blaxel cloud sandbox via smolagents.

    Args:
        sandbox_name: Name of the Blaxel sandbox instance.
        image: Docker image to use in the sandbox.
        memory: Memory allocation in MB.
    """

    def __init__(
        self,
        sandbox_name: str | None = None,
        image: str = "blaxel/jupyter-notebook",
        memory: int = 4096,
    ) -> None:
        self.sandbox_name = sandbox_name
        self.image = image
        self.memory = memory
        self._executor: Any = None

    # ── Public API ─────────────────────────────────────────────────────

    def execute(self, code: str, timeout: int = 0) -> ExecutionResult:
        """Run *code* in a Blaxel cloud sandbox via smolagents.

        Args:
            code: Python source defining ``generate_resources() -> list[dict]``.
            timeout: Wall-clock seconds (unused — Blaxel manages its own TTL).

        Returns:
            :class:`ExecutionResult` with parsed FHIR resource dicts.
        """

        # ── Build the script ──────────────────────────────────────────
        packages = get_execution_packages()
        script = build_runner_script(code, pip_install_packages=packages)

        # ── Run via smolagents BlaxelExecutor ─────────────────────────
        executor = self._get_executor()

        logger.info("Running code in Blaxel sandbox via smolagents")

        try:
            output = executor.run_code_raise_errors(script)
        except Exception as exc:
            raise RuntimeError(f"Blaxel execution error: {exc}") from exc

        stdout_text = output.logs.strip() if output.logs else ""

        if not stdout_text:
            raise RuntimeError("Blaxel sandbox produced no output")

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
        """Lazy-init the smolagents BlaxelExecutor."""
        if self._executor is not None:
            return self._executor

        try:
            from smolagents import BlaxelExecutor as SmolagentsBlaxelExecutor
        except ImportError:
            raise ImportError(
                "BlaxelExecutor requires the 'blaxel-core' package. "
                'Install it with: pip install "smolagents[blaxel]"'
            )

        packages = get_execution_packages()

        kwargs: dict[str, Any] = {
            "additional_imports": [
                p.split(">")[0].split("<")[0].split("=")[0].strip() for p in packages
            ],
            "logger": logger,
            "image": self.image,
            "memory": self.memory,
        }
        if self.sandbox_name:
            kwargs["sandbox_name"] = self.sandbox_name

        self._executor = SmolagentsBlaxelExecutor(**kwargs)
        return self._executor

    def cleanup(self) -> None:
        """Clean up Blaxel resources."""
        if self._executor is not None:
            self._executor.cleanup()
            self._executor = None
