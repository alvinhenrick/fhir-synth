"""E2B executor — powered by smolagents.

Runs LLM-generated code in an `E2B <https://e2b.dev>`_ cloud sandbox
via smolagents' ``E2BExecutor``.  E2B provides fully isolated micro-VMs
with pre-installed Python environments.

Requires the ``e2b-code-interpreter`` package and an ``E2B_API_KEY``::

    pip install "fhir-synth[e2b]"
    export E2B_API_KEY=e2b_...
"""

import json
import logging
import os
from typing import Any

from fhir_synth.code_generator.executor.base import (
    ExecutionResult,
    get_execution_packages,
    get_smolagents_logger,
)
from fhir_synth.code_generator.executor.validation import build_runner_script

logger = logging.getLogger(__name__)


class E2BExecutor:
    """Execute generated code in an E2B cloud sandbox via smolagents.

    The API key is resolved in order:

    1. ``api_key`` constructor argument
    2. ``E2B_API_KEY`` environment variable

    Args:
        api_key: E2B API key. Falls back to ``E2B_API_KEY`` env var.
        timeout: Execution timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.environ.get("E2B_API_KEY", "")
        self.timeout = timeout
        self._executor: Any = None

    # ── Public API ─────────────────────────────────────────────────────

    def execute(self, code: str, timeout: int = 0) -> ExecutionResult:
        """Run *code* in an E2B cloud sandbox via smolagents.

        Args:
            code: Python source defining ``generate_resources() -> list[dict]``.
            timeout: Wall-clock seconds. ``0`` means use the default.

        Returns:
            :class:`ExecutionResult` with parsed FHIR resource dicts.
        """
        timeout = timeout or self.timeout

        # smolagents installs packages during E2BExecutor init via
        # install_packages(), so no pip_install_packages needed here.
        script = build_runner_script(code)

        # ── Run via smolagents E2BExecutor ────────────────────────────
        executor = self._get_executor()

        logger.info("Running code in E2B sandbox via smolagents")

        try:
            output = executor.run_code_raise_errors(script)
        except Exception as exc:
            raise RuntimeError(f"E2B execution error: {exc}") from exc

        stdout_text = output.logs.strip() if output.logs else ""

        if not stdout_text:
            raise RuntimeError("E2B sandbox produced no output")

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
        """Lazy-init the smolagents E2BExecutor."""
        if self._executor is not None:
            return self._executor

        try:
            from smolagents import E2BExecutor as SmolagentsE2BExecutor
        except ImportError:
            raise ImportError(
                "E2BExecutor requires the 'e2b-code-interpreter' package. "
                'Install it with: pip install "smolagents[e2b]"'
            )

        if not self.api_key:
            raise ValueError(
                "E2B_API_KEY is required. Set it as an environment variable "
                "or pass api_key to E2BExecutor()."
            )

        packages = get_execution_packages()

        self._executor = SmolagentsE2BExecutor(
            additional_imports=[
                p.split(">")[0].split("<")[0].split("=")[0].strip() for p in packages
            ],
            logger=get_smolagents_logger(),
            api_key=self.api_key,
        )
        return self._executor

    def cleanup(self) -> None:
        """Clean up E2B resources."""
        if self._executor is not None:
            self._executor.cleanup()
            self._executor = None
