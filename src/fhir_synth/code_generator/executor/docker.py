"""Docker executor.

Runs LLM-generated code inside an ephemeral Docker container.  The
``fhir.resources`` and ``pydantic`` packages are either pre-installed in the
image or installed at runtime (``auto_install=True``).

Requires the ``docker`` Python SDK:

    pip install "fhir-synth[docker]"
"""

import json
import logging
import textwrap
from typing import Any

from fhir_synth.code_generator.executor.base import ExecutionResult
from fhir_synth.code_generator.executor.validation import (
    check_dangerous_code,
    fix_naive_date_times,
    validate_imports_whitelist,
)

logger = logging.getLogger(__name__)

# Default lightweight Python image
_DEFAULT_IMAGE = "python:3.12-slim"

# Packages that must be available inside the container
_REQUIRED_PACKAGES = [
    "fhir.resources>=7.0",
    "pydantic>=2.0",
    "python-dateutil>=2.8",
]


class DockerExecutor:
    """Execute generated code inside a Docker container.

    Args:
        image: Docker image to use. Defaults to ``python:3.12-slim``.
        auto_install: If ``True``, pip-install required packages before
            running the user code.  Set to ``False`` if the image already
            contains them.
        timeout: Default execution timeout in seconds.
    """

    def __init__(
        self,
        image: str = _DEFAULT_IMAGE,
        auto_install: bool = True,
        timeout: int = 60,
    ) -> None:
        self.image = image
        self.auto_install = auto_install
        self.default_timeout = timeout
        self._client: Any = None  # lazy docker.DockerClient

    # ── Public API ─────────────────────────────────────────────────────

    def execute(self, code: str, timeout: int = 0) -> ExecutionResult:
        """Run *code* inside a Docker container.

        Args:
            code: Python source defining ``generate_resources() -> list[dict]``.
            timeout: Wall-clock seconds. ``0`` means use the default.

        Returns:
            :class:`ExecutionResult` with parsed FHIR resource dicts.
        """
        timeout = timeout or self.default_timeout

        # ── Pre-flight safety checks ──────────────────────────────────
        dangerous = check_dangerous_code(code)
        if dangerous:
            raise ValueError(f"Code rejected — {'; '.join(dangerous)}")

        import_errors = validate_imports_whitelist(code)
        if import_errors:
            raise ValueError(f"Disallowed imports: {'; '.join(import_errors)}")

        code = fix_naive_date_times(code)

        # ── Build the script that runs inside the container ───────────
        script = self._build_script(code)

        # ── Run in Docker ─────────────────────────────────────────────
        client = self._get_client()

        logger.info("Running code in Docker container (image=%s)", self.image)

        try:
            container = client.containers.run(
                self.image,
                command=["python", "-c", script],
                detach=True,
                mem_limit="512m",
                network_disabled=True,
                remove=False,
            )

            # Wait for the container to finish
            result = container.wait(timeout=timeout)
            stdout_bytes: bytes = container.logs(stdout=True, stderr=False)
            stderr_bytes: bytes = container.logs(stdout=False, stderr=True)
            container.remove(force=True)

            stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
            exit_code: int = result.get("StatusCode", -1)

            if exit_code != 0:
                error_detail = stderr_text or stdout_text or "Unknown error"
                raise RuntimeError(f"Docker container exited with code {exit_code}: {error_detail}")

            if not stdout_text:
                raise RuntimeError("Container produced no output")

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

        except Exception as exc:
            if "timeout" in str(exc).lower() or "read timed out" in str(exc).lower():
                raise TimeoutError(f"Docker execution timed out after {timeout}s") from exc
            raise

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_client(self) -> Any:
        """Lazy-init the Docker SDK client."""
        if self._client is None:
            try:
                import docker  # type: ignore[import-untyped]
            except ImportError:
                raise ImportError(
                    "DockerExecutor requires the 'docker' package. "
                    'Install it with: pip install "fhir-synth[docker]"'
                )
            self._client = docker.from_env()
        return self._client

    def _build_script(self, code: str) -> str:
        """Build the full Python script that runs inside the container."""
        parts: list[str] = []

        # Optional: install dependencies at runtime
        if self.auto_install:
            pkgs = " ".join(f'"{p}"' for p in _REQUIRED_PACKAGES)
            parts.append(
                textwrap.dedent(f"""\
                    import subprocess, sys
                    subprocess.check_call(
                        [sys.executable, "-m", "pip", "install", "--quiet",
                         "--disable-pip-version-check", {pkgs}],
                        stdout=subprocess.DEVNULL,
                    )
                """)
            )

        # The actual user code + runner
        parts.append(
            textwrap.dedent("""\
                import json as _json
                import sys as _sys

                _user_code = {user_code_repr}
                _glb = {{}}
                exec(compile(_user_code, "<generated>", "exec"), _glb)

                if "generate_resources" not in _glb:
                    print(_json.dumps({{"__error__": "Code must define generate_resources()"}}))
                    _sys.exit(1)

                _result = _glb["generate_resources"]()
                if not isinstance(_result, list):
                    _result = [_result]

                if not _result:
                    print(_json.dumps({{"__error__": "generate_resources() returned empty list"}}))
                    _sys.exit(1)

                for _i, _r in enumerate(_result[:5]):
                    if not isinstance(_r, dict):
                        print(_json.dumps({{"__error__": f"Resource {{_i}} is {{type(_r).__name__}}, expected dict"}}))
                        _sys.exit(1)
                    if "resourceType" not in _r:
                        print(_json.dumps({{"__error__": f"Resource {{_i}} missing 'resourceType'"}}))
                        _sys.exit(1)

                print(_json.dumps(_result, default=str))
            """).format(user_code_repr=repr(code))
        )

        return "\n".join(parts)
