"""Executor package — pluggable backends for running LLM-generated code.

All backends are powered by `smolagents <https://huggingface.co/docs/smolagents>`_
for secure code execution:

- :class:`LocalSmolagentsExecutor` — AST-level secure interpreter (default).
- :class:`DockerSandboxExecutor` — Docker container via smolagents.
- :class:`E2BExecutor` — E2B cloud sandbox via smolagents.
- :class:`BlaxelExecutor` — Blaxel cloud sandbox via smolagents.

All backends share the :class:`Executor` protocol and return an :class:`ExecutionResult`.
"""

# ── Protocol & types ───────────────────────────────────────────────────────
from fhir_synth.code_generator.executor.base import (
    ExecutionResult,
    Executor,
    ExecutorBackend,
    get_execution_packages,
    get_executor,
)

# ── Backends ───────────────────────────────────────────────────────────────
from fhir_synth.code_generator.executor.blaxel import BlaxelExecutor
from fhir_synth.code_generator.executor.docker import DockerSandboxExecutor
from fhir_synth.code_generator.executor.e2b import E2BExecutor
from fhir_synth.code_generator.executor.local import LocalSmolagentsExecutor

# ── Shared validation (importable from here for convenience) ────
from fhir_synth.code_generator.executor.validation import (
    build_runner_script,
    fix_common_imports,
    validate_code,
    validate_imports,
)

__all__ = [
    # Protocol & types
    "Executor",
    "ExecutionResult",
    "ExecutorBackend",
    "get_execution_packages",
    "get_executor",
    # Backends
    "LocalSmolagentsExecutor",
    "DockerSandboxExecutor",
    "E2BExecutor",
    "BlaxelExecutor",
    # Validation
    "build_runner_script",
    "fix_common_imports",
    "validate_code",
    "validate_imports",
]
