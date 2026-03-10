"""Local subprocess executor.

Runs LLM-generated code in an isolated **subprocess** on the host machine.
Pre-flight checks (import whitelist, dangerous-pattern scan) are applied
before the subprocess is launched.
"""

import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from fhir_synth.code_generator.executor.base import ExecutionResult
from fhir_synth.code_generator.executor.validation import (
    build_runner_script,
    check_dangerous_code,
    validate_imports_whitelist,
)

logger = logging.getLogger(__name__)


class LocalSubprocessExecutor:
    """Execute generated code in a local subprocess with safety checks.

    Security layers:

    1. **Import whitelist** (AST-level) – only modules in the allowed set.
    2. **Dangerous-builtins regex** – blocks ``eval()``, ``exec()``, etc.
    3. **Subprocess isolation** – hard wall-clock timeout + crash containment.
    """

    def execute(self, code: str, timeout: int = 30) -> ExecutionResult:
        """Run *code* in an isolated subprocess.

        Args:
            code: Python source defining ``generate_resources() -> list[dict]``.
            timeout: Maximum wall-clock seconds.

        Returns:
            class:`ExecutionResult` with parsed FHIR resource dicts.

        Raises:
            ValueError: Code rejected by safety checks.
            TimeoutError: Execution exceeded *timeout*.
            RuntimeError: Subprocess exited with non-zero status.
        """
        # ── Pre-flight safety checks ──────────────────────────────────
        dangerous = check_dangerous_code(code)
        if dangerous:
            raise ValueError(f"Code rejected — {'; '.join(dangerous)}")

        import_errors = validate_imports_whitelist(code)
        if import_errors:
            raise ValueError(f"Disallowed imports: {'; '.join(import_errors)}")

        # ── Build the wrapper that runs inside the subprocess ─────────
        wrapper = build_runner_script(code)

        # ── Write to a temp file & run ─────────────────────────────────
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", prefix="fhir_synth_", delete=False
        )
        try:
            tmp.write(wrapper)
            tmp.flush()
            tmp.close()

            result = subprocess.run(  # noqa: S603
                [sys.executable, tmp.name],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            stderr_text = result.stderr.strip()
            stdout_text = result.stdout.strip()

            if result.returncode != 0:
                artifacts = self._parse_error(stdout_text, stderr_text, timeout)
                # _parse_error always raises — this is just for type safety
                return ExecutionResult(
                    stdout=stdout_text, stderr=stderr_text, artifacts=artifacts
                )  # pragma: no cover

            if not stdout_text:
                raise RuntimeError("Generated code produced no output")

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

        except subprocess.TimeoutExpired:
            raise TimeoutError(
                f"Code execution timed out after {timeout}s — possible infinite loop"
            ) from None
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_error(stdout: str, stderr: str, timeout: int) -> list[dict[str, Any]]:
        """Extract a meaningful error from subprocess output and raise."""
        # Check stdout for structured __error__ JSON
        if stdout:
            try:
                err_data = json.loads(stdout)
                if isinstance(err_data, dict) and "__error__" in err_data:
                    raise ValueError(err_data["__error__"])
            except json.JSONDecodeError:
                pass

        if not stderr:
            raise RuntimeError("Unknown error")

        lines = stderr.split("\n")
        meaningful: list[str] = []
        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("For further information"):
                continue
            meaningful.append(stripped)
            if len(meaningful) >= 3:
                break
        meaningful.reverse()
        raise RuntimeError("\n".join(meaningful))
