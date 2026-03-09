"""E2B Code Interpreter executor.

Runs LLM-generated code in an `E2B <https://e2b.dev>`_ cloud sandbox.
E2B provides fully isolated micro-VMs with pre-installed Python environments.

Requires the ``e2b-code-interpreter`` package and an ``E2B_API_KEY``::

    pip install "fhir-synth[e2b]"
    export E2B_API_KEY=e2b_...
"""

import json
import logging
import os

from fhir_synth.code_generator.executor.base import ExecutionResult, get_execution_packages
from fhir_synth.code_generator.executor.validation import (
    build_runner_script,
    check_dangerous_code,
    validate_imports_whitelist,
    fix_naive_date_times,
)

logger = logging.getLogger(__name__)


class E2BExecutor:
    """Execute generated code in an E2B cloud sandbox.

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

    # ── Public API ─────────────────────────────────────────────────────

    def execute(self, code: str, timeout: int = 0) -> ExecutionResult:
        """Run *code* in an E2B cloud sandbox.

        Args:
            code: Python source defining ``generate_resources() -> list[dict]``.
            timeout: Wall-clock seconds. ``0`` means use the default.

        Returns:
            class:`ExecutionResult` with parsed FHIR resource dicts.
        """
        timeout = timeout or self.timeout

        # ── Pre-flight safety checks ──────────────────────────────────
        dangerous = check_dangerous_code(code)
        if dangerous:
            raise ValueError(f"Code rejected — {'; '.join(dangerous)}")

        import_errors = validate_imports_whitelist(code)
        if import_errors:
            raise ValueError(f"Disallowed imports: {'; '.join(import_errors)}")

        # ── Normalize naive datetime patterns ───────────────────────────
        code = fix_naive_date_times(code)

        # ── Build the script ──────────────────────────────────────────
        script = self._build_script(code)

        # ── Run in E2B sandbox ────────────────────────────────────────
        try:
            from e2b_code_interpreter import Sandbox  # type: ignore[import-not-found]
        except ImportError:
            raise ImportError(
                "E2BExecutor requires the 'e2b-code-interpreter' package. "
                'Install it with: pip install "fhir-synth[e2b]"'
            )

        if not self.api_key:
            raise ValueError(
                "E2B_API_KEY is required. Set it as an environment variable "
                "or pass api_key to E2BExecutor()."
            )

        logger.info("Running code in E2B sandbox")

        sandbox = Sandbox(api_key=self.api_key, timeout=timeout)
        try:
            # Install required packages
            packages = get_execution_packages()
            if packages:
                pkg_str = " ".join(f'"{p}"' for p in packages)
                install_result = sandbox.run_code(
                    f"import subprocess, sys; subprocess.check_call("
                    f"[sys.executable, '-m', 'pip', 'install', '--quiet', "
                    f"'--disable-pip-version-check', {pkg_str}], "
                    f"stdout=subprocess.DEVNULL)"
                )
                if install_result.error:
                    logger.warning("Package install warning: %s", install_result.error)

            # Execute the user script
            result = sandbox.run_code(script)

            stdout_text = "".join(log.line for log in (result.logs.stdout or [])).strip()
            stderr_text = "".join(log.line for log in (result.logs.stderr or [])).strip()

            if result.error:
                raise RuntimeError(
                    f"E2B execution error: {result.error.name}: {result.error.value}"
                )

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
                stderr=stderr_text,
                artifacts=data,
            )
        finally:
            sandbox.kill()

    # ── Helpers ────────────────────────────────────────────────────────

    def _build_script(self, code: str) -> str:
        """Build the full Python script that runs inside the sandbox."""
        return build_runner_script(code)
