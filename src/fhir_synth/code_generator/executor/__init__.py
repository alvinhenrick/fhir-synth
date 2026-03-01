"""Executor package — pluggable backends for running LLM-generated code.

Provides three backends:

- :class:`LocalSubprocessExecutor` — runs code in a local subprocess (default).
- :class:`DockerExecutor` — runs code in an ephemeral Docker container.
- :class:`DifySandboxExecutor` — sends code to a dify-sandbox HTTP service.

All backends share the :class:`Executor` protocol and return an
:class:`ExecutionResult`.
"""

# ── Protocol & types ───────────────────────────────────────────────────────
from fhir_synth.code_generator.executor.base import (
    ExecutionResult,
    Executor,
    ExecutorBackend,
    get_executor,
)

# ── Backends ───────────────────────────────────────────────────────────────
from fhir_synth.code_generator.executor.dify import DifySandboxExecutor
from fhir_synth.code_generator.executor.docker import DockerExecutor
from fhir_synth.code_generator.executor.local import LocalSubprocessExecutor

# ── Shared validation (importable from here for backward compatibility) ────
from fhir_synth.code_generator.executor.validation import (
    check_dangerous_code,
    fix_common_imports,
    fix_naive_date_times,
    validate_code,
    validate_imports,
    validate_imports_whitelist,
)

# ── Backward-compatible function alias ─────────────────────────────────────
# Old code does: from fhir_synth.code_generator.executor import execute_code
_default_executor = LocalSubprocessExecutor()


def execute_code(code: str, timeout: int = 30) -> list[dict]:
    """Run *code* using the default local subprocess executor.

    This is a backward-compatible wrapper around
    :meth:`LocalSubprocessExecutor.execute`.
    """
    result = _default_executor.execute(code, timeout=timeout)
    return result.artifacts


# Keep the old private names importable
_check_dangerous_code = check_dangerous_code
_validate_imports_whitelist = validate_imports_whitelist

__all__ = [
    # Protocol & types
    "Executor",
    "ExecutionResult",
    "ExecutorBackend",
    "get_executor",
    # Backends
    "LocalSubprocessExecutor",
    "DockerExecutor",
    "DifySandboxExecutor",
    # Validation
    "check_dangerous_code",
    "fix_common_imports",
    "fix_naive_date_times",
    "validate_code",
    "validate_imports",
    "validate_imports_whitelist",
    # Backward compatibility
    "execute_code",
    "_check_dangerous_code",
    "_validate_imports_whitelist",
]
