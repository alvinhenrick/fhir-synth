"""Shared validation helpers for code execution.

FHIR-specific validation and auto-fix utilities.  Security enforcement
(import whitelisting, dangerous builtin blocking) is handled by smolagents.
"""

import ast
import importlib.util
import logging
import re
import textwrap

from fhir_synth.fhir_spec import class_to_module

logger = logging.getLogger(__name__)


# ── Code validation (syntax only) ─────────────────────────────────────────


def validate_code(code: str) -> bool:
    """Validate that generated code is syntactically correct.

    Security enforcement (import whitelisting, dangerous builtins) is
    handled by smolagents at execution time.

    Returns:
        True if valid Python syntax, False otherwise.
    """
    try:
        ast.parse(code)
    except SyntaxError:
        return False
    return True


# ── Import correctness (fhir.resources modules exist?) ─────────────────────


def validate_imports(code: str) -> list[str]:
    """Validate that `fhir.resources` imports reference real modules.

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


def strip_future_imports(code: str) -> str:
    """Remove `from __future__ import ...` lines.

    smolagents' AST executor does not allow ``__future__`` imports (they are
    not in the authorized-imports list and cannot be added).  LLMs occasionally
    emit them (e.g. ``from __future__ import annotations``), causing an
    "Import from __future__ is not allowed" error at execution time.
    Stripping them is safe because the generated code targets Python 3.10+
    where all relevant ``__future__`` features are built-in.
    """
    lines = code.splitlines(keepends=True)
    return "".join(line for line in lines if not line.lstrip().startswith("from __future__"))


def fix_common_imports(code: str) -> str:
    """Auto-fix import mistakes using the introspected class→module map.

    Rewrites `from fhir.resources.R4B.{wrong} import {Cls}` to the
    correct module for each class.  Also strips ``from __future__`` imports
    which smolagents does not allow.

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

    return strip_future_imports(_IMPORT_RE.sub(_fix_line, code))


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


def build_runner_script(code: str) -> str:
    """Build the Python script that wraps user code for execution.

    This is the single source of truth for the runner used by all remote
    executor backends (Docker, E2B, Blaxel).  It exec's the user code,
    calls `generate_resources()`, validates the output, and prints JSON
    to stdout.

    Package installation is handled by smolagents during executor init
    (via `install_packages()`), so this function only wraps the code.

    Args:
        code: The user-generated Python source code.
    """
    return _RUNNER_TEMPLATE.format(user_code_repr=repr(code))
