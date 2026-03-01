"""Executor protocol and result model.

All executor backends implement the: class:`Executor` protocol so that
calling code is backend-agnostic.
"""

import enum
from dataclasses import dataclass, field
from importlib.metadata import requires
from typing import Any, Protocol, runtime_checkable

# Packages needed inside remote/container executors for running generated code.
# Only a subset of the project's full dependencies — CLI/LLM packages are not needed.
_EXECUTION_PACKAGE_NAMES = frozenset({"fhir.resources", "pydantic", "python-dateutil"})


def get_execution_packages() -> list[str]:
    """Read execution-relevant dependencies from installed fhir-synth metadata.

    Returns pinned specs like ``["fhir-resources>=7.0", "pydantic>=2.0", ...]``
    by filtering the project's declared dependencies (from ``pyproject.toml``)
    to only those needed for running generated code inside a container or
    sandbox.  CLI, LLM, and dev packages are excluded.
    """
    try:
        reqs = requires("fhir-synth") or []
    except Exception:
        # Fallback if package metadata is unavailable (e.g. editable install quirk)
        return sorted(_EXECUTION_PACKAGE_NAMES)

    # Build a normalized lookup set (PEP 503: dots/underscores → dashes, lowercase)
    normalized_names = {
        name.replace(".", "-").replace("_", "-").lower() for name in _EXECUTION_PACKAGE_NAMES
    }

    packages: list[str] = []
    for req in reqs:
        # Skip optional/extra dependencies (they contain "; extra ==")
        if "; " in req:
            continue
        # Extract the package name (before any version specifier)
        raw_name = req.split(">")[0].split("<")[0].split("=")[0].split("!")[0].split("[")[0].strip()
        normalized = raw_name.replace(".", "-").replace("_", "-").lower()
        if normalized in normalized_names:
            packages.append(req.strip())
    return packages or sorted(_EXECUTION_PACKAGE_NAMES)


class ExecutorBackend(enum.StrEnum):
    """Supported executor backends."""

    LOCAL = "local"
    DIFY = "dify"
    E2B = "e2b"


@dataclass
class ExecutionResult:
    """Uniform result returned by every executor backend.

    Attributes:
        stdout: Raw standard output from the execution.
        stderr: Raw standard error from the execution.
        artifacts: Parsed list of FHIR resource dicts (the real payload).
    """

    stdout: str = ""
    stderr: str = ""
    artifacts: list[dict[str, Any]] = field(default_factory=list)


@runtime_checkable
class Executor(Protocol):
    """Protocol that every executor backend must satisfy."""

    def execute(self, code: str, timeout: int = 30) -> ExecutionResult:
        """Execute *code* and return an: class:`ExecutionResult`.

        Args:
            code: Python source that defines ``generate_resources() -> list[dict]``.
            timeout: Maximum wall-clock seconds before the process is killed.

        Returns:
            An :class:`ExecutionResult` with stdout, stderr, and parsed artifacts.

        Raises:
            ValueError: If the code is rejected by pre-flight safety checks.
            TimeoutError: If execution exceeds *timeout* seconds.
            RuntimeError: If the code exits with a non-zero status.
        """
        ...


def get_executor(
    backend: str | ExecutorBackend = ExecutorBackend.LOCAL,
    *,
    dify_url: str | None = None,
    e2b_api_key: str | None = None,
) -> Executor:
    """Factory that returns a concrete executor for the requested backend.

    Args:
        backend: One of ``"local"``, ``"dify"``, or ``"e2b"`` (or an
            :class:`ExecutorBackend` enum member).
        dify_url: Base URL for the dify-sandbox service (only used when
            *backend* is ``"dify"``).
        e2b_api_key: API key for E2B (only used when *backend* is ``"e2b"``).
            Falls back to ``E2B_API_KEY`` env var.

    Returns:
        An object satisfying the: class:`Executor` protocol.

    Raises:
        ValueError: If *backend* is not recognized.
        ImportError: If the backend requires an optional dependency, that is
            not installed.
    """
    if isinstance(backend, str):
        try:
            backend = ExecutorBackend(backend.lower())
        except ValueError:
            valid = ", ".join(b.value for b in ExecutorBackend)
            raise ValueError(f"Unknown executor backend {backend!r}. Choose from: {valid}")

    if backend is ExecutorBackend.LOCAL:
        from fhir_synth.code_generator.executor.local import LocalSubprocessExecutor

        return LocalSubprocessExecutor()

    if backend is ExecutorBackend.DIFY:
        from fhir_synth.code_generator.executor.dify import DifySandboxExecutor

        kwargs: dict[str, Any] = {}
        if dify_url:
            kwargs["base_url"] = dify_url
        return DifySandboxExecutor(**kwargs)

    if backend is ExecutorBackend.E2B:
        from fhir_synth.code_generator.executor.e2b import E2BExecutor

        kwargs = {}
        if e2b_api_key:
            kwargs["api_key"] = e2b_api_key
        return E2BExecutor(**kwargs)

    # Should be unreachable
    raise ValueError(f"Unhandled backend: {backend}")
