"""Local secure executor — powered by smolagents.

Runs LLM-generated code via smolagents'
`evaluate_python_code <https://huggingface.co/docs/smolagents/tutorials/secure_code_execution>`_
which interprets code at the AST level with fine-grained import control
and a restricted set of built-in functions.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from smolagents.local_python_executor import (
    BASE_BUILTIN_MODULES,
    BASE_PYTHON_TOOLS,
    ExecutionTimeoutError,
    InterpreterError,
    evaluate_python_code,
)

from fhir_synth.code_generator.constants import ALLOWED_MODULE_PREFIXES, ALLOWED_MODULES
from fhir_synth.code_generator.executor.base import ExecutionResult

logger = logging.getLogger(__name__)

# Modules that the secure interpreter is allowed to import.
# Combines smolagents defaults with the project-wide allowed list
# from constants.py + FHIR / data-generation wildcard prefixes.
_AUTHORIZED_IMPORTS: list[str] = (
    list(BASE_BUILTIN_MODULES)
    + sorted(ALLOWED_MODULES)
    + [f"{p}.*" for p in ALLOWED_MODULE_PREFIXES]
    + ["dateutil.*"]
)

# Append to the generated code so that evaluate_python_code returns the
# FHIR resource list as its output value.
_INVOKE_SUFFIX = """
try:
    _fn = generate_resources
except NameError:
    raise ValueError("Code must define generate_resources()")

_result = _fn()
if not isinstance(_result, list):
    _result = [_result]

if not _result:
    raise ValueError(
        "generate_resources() returned empty list "
        "— it must return at least one resource dict"
    )

for _i, _r in enumerate(_result[:5]):
    if not isinstance(_r, dict):
        raise ValueError(
            f"Resource {_i} is {type(_r).__name__}, expected dict "
            "— use .model_dump(exclude_none=True) on Pydantic models"
        )
    if "resourceType" not in _r:
        raise ValueError(
            f"Resource {_i} is missing 'resourceType' "
            f"(keys: {list(_r.keys())[:5]}) "
            "— use .model_dump(exclude_none=True) on Pydantic models"
        )

_result
"""


class LocalSmolagentsExecutor:
    """Execute generated code via smolagents' secure Python interpreter.

    All security is handled by smolagents:

    1. **AST-level execution** — every operation is interpreted node-by-node.
    2. **Import whitelist** — only explicitly authorized modules are importable.
    3. **Restricted builtins** — no ``open``, ``compile``, ``__import__``, etc.
    4. **Timeout** — hard wall-clock limit via ``concurrent.futures``.
    """

    def execute(self, code: str, timeout: int = 30) -> ExecutionResult:
        """Run *code* via smolagents' secure AST interpreter.

        Args:
            code: Python source defining ``generate_resources() -> list[dict]``.
            timeout: Maximum wall-clock seconds.

        Returns:
            :class:`ExecutionResult` with parsed FHIR resource dicts.

        Raises:
            TimeoutError: Execution exceeded *timeout*.
            RuntimeError: Code produced invalid output or was rejected by smolagents.
        """
        full_code = code + "\n" + _INVOKE_SUFFIX

        try:
            output, _is_final = evaluate_python_code(
                full_code,
                static_tools=dict(BASE_PYTHON_TOOLS),
                custom_tools={},
                authorized_imports=_AUTHORIZED_IMPORTS,
                timeout_seconds=timeout,
            )
        except ExecutionTimeoutError as exc:
            raise TimeoutError(
                f"Code execution timed out after {timeout}s — possible infinite loop"
            ) from exc
        except InterpreterError as exc:
            msg = str(exc)
            if "timed out" in msg.lower() or "timeout" in msg.lower():
                raise TimeoutError(
                    f"Code execution timed out after {timeout}s — possible infinite loop"
                ) from exc
            # Extract the original error message from smolagents wrapping
            # Pattern: "... due to: ErrorType: actual message"
            if "due to:" in msg:
                inner = msg.split("due to:", 1)[1].strip()
                if ": " in inner:
                    error_class, inner_msg = inner.split(": ", 1)
                    if "ValueError" in error_class:
                        raise ValueError(inner_msg) from exc
                    raise RuntimeError(inner_msg) from exc
            raise RuntimeError(msg) from exc

        return self._parse_output(output)

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_output(output: Any) -> ExecutionResult:
        """Convert smolagents output into an ExecutionResult."""
        if isinstance(output, list):
            data = output
        elif isinstance(output, str):
            data = json.loads(output)
        else:
            raise RuntimeError(
                f"Expected list from generate_resources(), got {type(output).__name__}"
            )

        if not isinstance(data, list):
            raise RuntimeError(
                f"Expected list from generate_resources(), got {type(data).__name__}"
            )

        return ExecutionResult(
            stdout=json.dumps(data, default=str),
            stderr="",
            artifacts=data,
        )
