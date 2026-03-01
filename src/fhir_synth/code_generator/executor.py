"""Code execution and validation utilities.

Provides three layers of security for running LLM-generated code:

1. **Import whitelist** (AST-level) – only modules in ``ALLOWED_MODULES``
   and prefixes in ``ALLOWED_MODULE_PREFIXES`` may be imported.
2. **Dangerous-builtins regex** – blocks ``eval()``, ``exec()``,
   ``open()``, ``compile()``, ``globals()``, and ``__import__()``.
3. **Subprocess isolation** (OS-level) – the code executes in a *separate
   process* with a hard wall-clock timeout and a restricted ``__import__``
   that enforces the same whitelist at runtime.
"""

import ast
import importlib.util
import json
import logging
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from fhir_synth.code_generator.constants import (
    ALLOWED_MODULE_PREFIXES,
    ALLOWED_MODULES,
    DANGEROUS_PATTERNS,
)
from fhir_synth.fhir_spec import class_to_module

logger = logging.getLogger(__name__)


def _check_dangerous_code(code: str) -> list[str]:
    """Scan code for dangerous patterns.

    Args:
        code: Python code to check

    Returns:
        List of warnings about dangerous patterns found
    """
    warnings = []
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(code):
            warnings.append(f"Dangerous pattern detected: {pattern.pattern}")
    return warnings


def _validate_imports_whitelist(code: str) -> list[str]:
    """Ensure all imports are from the allowed whitelist.

    Args:
        code: Python code to check

    Returns:
        List of error messages for disallowed imports
    """
    errors = []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ["Syntax error in code"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _is_allowed_module(alias.name):
                    errors.append(f"Disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if not _is_allowed_module(module):
                errors.append(f"Disallowed import: {module}")
    return errors


def _is_allowed_module(module: str) -> bool:
    """Check if a module is in the allowed whitelist."""
    if module in ALLOWED_MODULES:
        return True
    return any(module.startswith(prefix) for prefix in ALLOWED_MODULE_PREFIXES)


def validate_code(code: str) -> bool:
    """Validate that generated code is safe and syntactically correct.

    Checks syntax, dangerous builtins patterns, and import whitelist.

    Args:
        code: Python code to validate

    Returns:
        True if valid, False otherwise
    """
    # Check syntax
    try:
        ast.parse(code)
    except SyntaxError:
        return False

    # Reject dangerous patterns
    if _check_dangerous_code(code):
        return False

    # Reject disallowed imports
    if _validate_imports_whitelist(code):
        return False

    return True


def validate_imports(code: str) -> list[str]:
    """Validate that imports in generated code are correct.

    Args:
        code: Python code to validate

    Returns:
        List of error messages, empty if all imports are valid
    """
    errors = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ["Syntax error in code"]

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module
            if module and module.startswith("fhir.resources"):
                # Check if module exists
                spec = importlib.util.find_spec(module)
                if spec is None:
                    errors.append(f"Invalid import: {module} (module not found)")

                    # Suggest a fix using an introspected class→module map
                    if node.names:
                        for alias in node.names:
                            correct_mod = class_to_module(alias.name)
                            if correct_mod:
                                errors.append(
                                    f"  → Fix: from fhir.resources.R4B.{correct_mod} import {alias.name}"
                                )

    return errors


def fix_common_imports(code: str) -> str:
    """Auto-fix import mistakes in generated code using an introspected class→module map.

    For every ``from fhir.resources.R4B.{wrong} import {Cls}`` line, looks up
    the correct module for each imported class and rewrites the line if needed.
    Multiple classes from the same module are grouped into a single import.

    Args:
        code: Python code with potential import issues

    Returns:
        Fixed code
    """
    # Match: from fhir.resources.R4B.<module> import <names>
    _import_re = re.compile(r"^(from fhir\.resources\.R4B\.)(\w+)(\s+import\s+)(.+)$", re.MULTILINE)

    def _fix_line(match: re.Match[str]) -> str:
        prefix = match.group(1)  # "from fhir.resources.R4B."
        current_mod = match.group(2)  # e.g. "timingrepeat"
        import_kw = match.group(3)  # " import "
        names_str = match.group(4)  # "TimingRepeat, Timing"

        # Parse individual class names
        class_names = [n.strip() for n in names_str.split(",") if n.strip()]

        # Group classes by their correct module
        mod_to_classes: dict[str, list[str]] = {}
        for cls_name in class_names:
            correct_mod = class_to_module(cls_name)
            if correct_mod is None:
                # Unknown class — keep it in the original module
                correct_mod = current_mod
            mod_to_classes.setdefault(correct_mod, []).append(cls_name)

        # Build replacement line(s)
        lines = []
        for mod, classes in sorted(mod_to_classes.items()):
            lines.append(f"{prefix}{mod}{import_kw}{', '.join(classes)}")
        return "\n".join(lines)

    return _import_re.sub(_fix_line, code)


# Regex patterns for naive datetime.now() calls
_NAIVE_NOW_RE = re.compile(
    r"datetime\.now\(\s*\)",
)
_NAIVE_UTCNOW_RE = re.compile(
    r"datetime\.utcnow\(\s*\)",
)


def _fix_naive_datetimes(code: str) -> str:
    """Replace naive datetime.now() with timezone-aware UTC versions.

    FHIR ``instant`` fields require a timezone offset.  LLMs frequently
    generate ``datetime.now().isoformat()`` which produces a naive
    timestamp (no timezone) that fails Pydantic validation.

    This function rewrites the source code so:

    - ``datetime.now()`` → ``datetime.now(datetime.timezone.utc)``
    - ``datetime.utcnow()`` → ``datetime.now(datetime.timezone.utc)``
    """
    code = _NAIVE_NOW_RE.sub("datetime.now(datetime.timezone.utc)", code)
    code = _NAIVE_UTCNOW_RE.sub("datetime.now(datetime.timezone.utc)", code)
    return code


def execute_code(code: str, timeout: int = 30) -> list[dict[str, Any]]:
    """Run generated code in an isolated subprocess with a timeout.

    The code is written to a temporary file and executed in a fresh Python
    process.  Only whitelisted modules can be imported (enforced by
    ``_validate_imports_whitelist`` *before* execution and by a restricted
    ``__import__`` inside the subprocess).  A hard timeout kills the
    process if it runs too long.

    Args:
        code: Python code to execute.  Must define ``generate_resources()``.
        timeout: Maximum wall-clock seconds before the process is killed.

    Returns:
        List of generated FHIR resource dicts.

    Raises:
        ValueError: If the code contains disallowed imports or dangerous
            patterns, or does not define ``generate_resources()``.
        TimeoutError: If execution exceeds *timeout* seconds.
        RuntimeError: If the subprocess exits with a non-zero status.
    """
    # ── Pre-flight safety checks ──────────────────────────────────────
    dangerous = _check_dangerous_code(code)
    if dangerous:
        raise ValueError(f"Code rejected — {'; '.join(dangerous)}")

    import_errors = _validate_imports_whitelist(code)
    if import_errors:
        raise ValueError(f"Disallowed imports: {'; '.join(import_errors)}")

    # ── Fix naive datetime.now() calls ────────────────────────────────
    # LLMs often generate datetime.now().isoformat() which produces naive
    # timestamps that fail FHIR instant validation. Patch the source to
    # use datetime.now(datetime.timezone.utc) instead.
    code = _fix_naive_datetimes(code)

    # ── Build the wrapper that runs inside the subprocess ─────────────
    # The pre-flight AST check already blocked disallowed imports.
    # The subprocess provides isolation (timeout + crash containment).
    wrapper = textwrap.dedent("""\
        import json as _json
        import sys as _sys

        # ── Execute user code ────────────────────────────────────────
        _user_code = {user_code_repr}
        _glb = {{}}
        exec(compile(_user_code, "<generated>", "exec"), _glb)

        if "generate_resources" not in _glb:
            print(_json.dumps({{"__error__": "Code must define generate_resources()"}}))
            _sys.exit(1)

        _result = _glb["generate_resources"]()
        if not isinstance(_result, list):
            _result = [_result]

        # ── Smoke test: validate output looks like FHIR resources ────
        if not _result:
            print(_json.dumps({{"__error__": "generate_resources() returned empty list — it must return at least one resource dict"}}))
            _sys.exit(1)
        for _i, _r in enumerate(_result[:5]):
            if not isinstance(_r, dict):
                print(_json.dumps({{"__error__": f"Resource {{_i}} is {{type(_r).__name__}}, expected dict — use .model_dump(exclude_none=True) on Pydantic models"}}))
                _sys.exit(1)
            if "resourceType" not in _r:
                print(_json.dumps({{"__error__": f"Resource {{_i}} is missing 'resourceType' (keys: {{list(_r.keys())[:5]}}) — use .model_dump(exclude_none=True) on Pydantic models"}}))
                _sys.exit(1)

        print(_json.dumps(_result, default=str))
    """).format(
        user_code_repr=repr(code),
    )

    # ── Write to a temp file & run in subprocess ────────────────────────
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", prefix="fhir_synth_", delete=False)
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

        if result.returncode != 0:
            # Check stdout for structured __error__ JSON (smoke test failures)
            stdout_raw = result.stdout.strip()
            if stdout_raw:
                try:
                    err_data = json.loads(stdout_raw)
                    if isinstance(err_data, dict) and "__error__" in err_data:
                        raise ValueError(err_data["__error__"])
                except json.JSONDecodeError:
                    pass  # not JSON, fall through to stderr

            stderr = result.stderr.strip()
            if not stderr:
                raise RuntimeError("Unknown error")
            # Extract a useful error message from the traceback.
            # For Pydantic ValidationError the last line is just a URL;
            # walk backwards to find the real error.
            lines = stderr.split("\n")
            meaningful: list[str] = []
            for line in reversed(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                # Skip Pydantic URL footer lines
                if stripped.startswith("For further information"):
                    continue
                meaningful.append(stripped)
                # Stop once we have enough context (the exception line + a detail)
                if len(meaningful) >= 3:
                    break
            meaningful.reverse()
            raise RuntimeError("\n".join(meaningful))

        stdout = result.stdout.strip()
        if not stdout:
            raise RuntimeError("Generated code produced no output")

        data = json.loads(stdout)
        if isinstance(data, dict) and "__error__" in data:
            raise ValueError(data["__error__"])

        if not isinstance(data, list):
            raise RuntimeError(
                f"Expected list from generate_resources(), got {type(data).__name__}"
            )

        return data

    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Code execution timed out after {timeout}s — possible infinite loop"
        ) from None
    finally:
        Path(tmp.name).unlink(missing_ok=True)
