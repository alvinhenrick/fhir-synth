"""Executor package — pluggable backends for running LLM-generated code.

Provides three backends:

- :class:`LocalSubprocessExecutor` — runs code in a local subprocess (default).
- :class:`DifySandboxExecutor` — sends code to a self-hosted dify-sandbox service.
- :class:`E2BExecutor` — runs code in an E2B cloud sandbox.

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
from fhir_synth.code_generator.executor.dify import DifySandboxExecutor
from fhir_synth.code_generator.executor.e2b import E2BExecutor
from fhir_synth.code_generator.executor.local import LocalSubprocessExecutor

# ── Shared validation (importable from here for convenience) ────
from fhir_synth.code_generator.executor.validation import (
    build_runner_script,
    check_dangerous_code,
    fix_common_imports,
    validate_code,
    validate_imports,
    validate_imports_whitelist,
    fix_naive_date_times,
)

__all__ = [
    # Protocol & types
    "Executor",
    "ExecutionResult",
    "ExecutorBackend",
    "get_execution_packages",
    "get_executor",
    # Backends
    "LocalSubprocessExecutor",
    "DifySandboxExecutor",
    "E2BExecutor",
    # Validation
    "build_runner_script",
    "check_dangerous_code",
    "fix_common_imports",
    "validate_code",
    "validate_imports",
    "validate_imports_whitelist",
    "fix_naive_date_times",
]
