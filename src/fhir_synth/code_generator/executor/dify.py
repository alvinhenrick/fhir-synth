"""Dify Sandbox executor.

Runs LLM-generated code by sending it to a
`dify-sandbox <https://github.com/langgenius/dify-sandbox>`_ service over
HTTP.  The sandbox provides OS-level isolation (seccomp, namespaces) and
is easy to self-host via Docker.

Start the sandbox locally::

    docker run -d -p 8194:8194 langgenius/dify-sandbox:latest

Requires ``httpx``::

    pip install "fhir-synth[sandbox]"
"""

import json
import logging
import os
import textwrap
from typing import Any

from fhir_synth.code_generator.executor.base import ExecutionResult
from fhir_synth.code_generator.executor.validation import (
    check_dangerous_code,
    fix_naive_date_times,
    validate_imports_whitelist,
)

logger = logging.getLogger(__name__)

_DEFAULT_URL = "http://localhost:8194"


class DifySandboxExecutor:
    """Execute generated code via the dify-sandbox HTTP API.

    Args:
        base_url: Base URL of the dify-sandbox service.
        api_key: API key for authentication (header ``X-Api-Key``).
            Falls back to the ``DIFY_SANDBOX_API_KEY`` env var.
        timeout: HTTP request timeout in seconds.
        preinstall_packages: Packages to install before running the code.
            Defaults to the FHIR packages needed by generated code.
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_URL,
        api_key: str | None = None,
        timeout: int = 120,
        preinstall_packages: list[str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("DIFY_SANDBOX_API_KEY", "")
        self.timeout = timeout
        self.preinstall_packages = preinstall_packages or [
            "fhir.resources>=7.0",
            "pydantic>=2.0",
            "python-dateutil>=2.8",
        ]
        self._client: Any = None  # lazy httpx.Client

    # ── Public API ─────────────────────────────────────────────────────

    def execute(self, code: str, timeout: int = 0) -> ExecutionResult:
        """Send *code* to dify-sandbox for execution.

        Args:
            code: Python source defining ``generate_resources() -> list[dict]``.
            timeout: Override timeout (0 = use default).

        Returns:
            :class:`ExecutionResult` with parsed FHIR resource dicts.
        """
        timeout = timeout or self.timeout

        # ── Pre-flight safety checks ──────────────────────────────────
        dangerous = check_dangerous_code(code)
        if dangerous:
            raise ValueError(f"Code rejected — {'; '.join(dangerous)}")

        import_errors = validate_imports_whitelist(code)
        if import_errors:
            raise ValueError(f"Disallowed imports: {'; '.join(import_errors)}")

        code = fix_naive_date_times(code)

        # ── Build the full script ─────────────────────────────────────
        script = self._build_script(code)

        # ── Send to dify-sandbox ──────────────────────────────────────
        client = self._get_client()

        logger.info("Sending code to dify-sandbox at %s", self.base_url)

        response = client.post(
            f"{self.base_url}/v1/sandbox/run",
            json={
                "language": "python3",
                "code": script,
                "preload": "",
            },
            headers={"X-Api-Key": self.api_key} if self.api_key else {},
            timeout=timeout,
        )
        response.raise_for_status()

        body = response.json()

        stdout_text = body.get("data", {}).get("stdout", "").strip()
        stderr_text = body.get("data", {}).get("stderr", "").strip()
        error = body.get("data", {}).get("error", "")

        if error:
            raise RuntimeError(f"Dify sandbox error: {error}")

        if not stdout_text:
            raise RuntimeError("Dify sandbox produced no output")

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

    # ── Helpers ────────────────────────────────────────────────────────

    def _get_client(self) -> Any:
        """Lazy-init the httpx client."""
        if self._client is None:
            try:
                import httpx  # type: ignore[import-untyped]
            except ImportError:
                raise ImportError(
                    "DifySandboxExecutor requires the 'httpx' package. "
                    'Install it with: pip install "fhir-synth[sandbox]"'
                )
            self._client = httpx.Client()
        return self._client

    def _build_script(self, code: str) -> str:
        """Build the full Python script sent to the sandbox."""
        parts: list[str] = []

        # Pre-install packages if configured
        if self.preinstall_packages:
            pkgs = " ".join(f'"{p}"' for p in self.preinstall_packages)
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

        # User code + runner
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
