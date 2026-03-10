"""Shared validation helpers for code execution.

These functions run **before** any backend executes code.  They are
backend-agnostic and can be reused by local, dify, and e2b executors.
"""

import ast
import importlib.util
import logging
import re
import textwrap

from fhir_synth.code_generator.constants import (
    ALLOWED_MODULE_PREFIXES,
    ALLOWED_MODULES,
    DANGEROUS_PATTERNS,
)
from fhir_synth.fhir_spec import class_to_module

logger = logging.getLogger(__name__)


# ── Dangerous-pattern scanning ─────────────────────────────────────────────


def check_dangerous_code(code: str) -> list[str]:
    """Scan *code* for dangerous built-in patterns.

    Returns:
        List of warnings about dangerous patterns found.
    """
    warnings: list[str] = []
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(code):
            warnings.append(f"Dangerous pattern detected: {pattern.pattern}")
    return warnings


# ── Import whitelist ───────────────────────────────────────────────────────


def _is_allowed_module(module: str) -> bool:
    """Check if *module* is in the allowed whitelist."""
    if module in ALLOWED_MODULES:
        return True
    return any(module.startswith(prefix) for prefix in ALLOWED_MODULE_PREFIXES)


def validate_imports_whitelist(code: str) -> list[str]:
    """Ensure all imports are from the allowed whitelist.

    Returns:
        List of error messages for disallowed imports.
    """
    errors: list[str] = []
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


# ── Code validation (syntax + danger + whitelist) ──────────────────────────


def validate_code(code: str) -> bool:
    """Validate that generated code is safe and syntactically correct.

    Returns:
        True if valid, False otherwise.
    """
    try:
        ast.parse(code)
    except SyntaxError:
        return False

    if check_dangerous_code(code):
        return False

    if validate_imports_whitelist(code):
        return False

    return True


# ── Import correctness (fhir.resources modules exist?) ─────────────────────


def validate_imports(code: str) -> list[str]:
    """Validate that ``fhir.resources`` imports reference real modules.

    Returns:
        List of error messages, empty if all imports are valid.
    """
    errors: list[str] = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ["Syntax error in code"]

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module
            if module and module.startswith("fhir.resources"):
                spec = importlib.util.find_spec(module)
                if spec is None:
                    errors.append(f"Invalid import: {module} (module not found)")

                    if node.names:
                        for alias in node.names:
                            correct_mod = class_to_module(alias.name)
                            if correct_mod:
                                errors.append(
                                    f"  → Fix: from fhir.resources.R4B.{correct_mod} import {alias.name}"
                                )
    return errors


# ── Auto-fix common import mistakes ───────────────────────────────────────

_IMPORT_RE = re.compile(r"^(from fhir\.resources\.R4B\.)(\w+)(\s+import\s+)(.+)$", re.MULTILINE)


def fix_common_imports(code: str) -> str:
    """Auto-fix import mistakes using the introspected class→module map.

    Rewrites ``from fhir.resources.R4B.{wrong} import {Cls}`` to the
    correct module for each class.

    Returns:
        Fixed code.
    """

    def _fix_line(match: re.Match[str]) -> str:
        prefix = match.group(1)
        current_mod = match.group(2)
        import_kw = match.group(3)
        names_str = match.group(4)

        class_names = [n.strip() for n in names_str.split(",") if n.strip()]

        mod_to_classes: dict[str, list[str]] = {}
        for cls_name in class_names:
            correct_mod = class_to_module(cls_name)
            if correct_mod is None:
                correct_mod = current_mod
            mod_to_classes.setdefault(correct_mod, []).append(cls_name)

        lines: list[str] = []
        for mod, classes in sorted(mod_to_classes.items()):
            lines.append(f"{prefix}{mod}{import_kw}{', '.join(classes)}")
        return "\n".join(lines)

    return _IMPORT_RE.sub(_fix_line, code)


# ── Shared runner script ───────────────────────────────────────────────────

_RUNNER_TEMPLATE = textwrap.dedent("""\
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
""")


def build_runner_script(code: str, *, pip_install_packages: list[str] | None = None) -> str:
    """Build the Python script that wraps user code for execution.

    This is the single source of truth for the runner used by all executor
    backends.  It exec's the user code, calls ``generate_resources()``,
    validates the output, and prints JSON to stdout.

    Args:
        code: The user-generated Python source code.
        pip_install_packages: Optional list of packages to pip-install
            before running the user code (used by remote executors).
    """
    parts: list[str] = []

    if pip_install_packages:
        pkgs = " ".join(f'"{p}"' for p in pip_install_packages)
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

    parts.append(_RUNNER_TEMPLATE.format(user_code_repr=repr(code)))
    return "\n".join(parts)
