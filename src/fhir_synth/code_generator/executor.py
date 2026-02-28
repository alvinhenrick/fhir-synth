"""Code execution and validation utilities.

Provides two layers of security for running LLM-generated code:

1. **RestrictedPython** (AST-level) – ``compile_restricted`` catches unsafe
   constructs (attribute mutation, builtins abuse, print hijacking) at
   *compile time*, before any code runs.
2. **Subprocess isolation** (OS-level) – the code executes in a *separate
   process* with a hard wall-clock timeout, so a runaway loop or crash
   cannot affect the parent.

Both layers share the same import whitelist (``_ALLOWED_MODULES`` /
``_ALLOWED_MODULE_PREFIXES``).
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

from RestrictedPython import compile_restricted
from RestrictedPython.Eval import default_guarded_getattr
from RestrictedPython.Guards import guarded_unpack_sequence, safe_globals

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


# ── RestrictedPython helpers ─────────────────────────────────────────────


def _strip_type_annotations(code: str) -> str:
    """Remove variable type annotations that RestrictedPython does not support.

    Converts ``x: int = 5`` → ``x = 5`` and removes bare annotations
    like ``x: int`` (no value).  Function parameter annotations and
    return annotations are left alone — RestrictedPython handles those.

    Args:
        code: Python source code.

    Returns:
        Code with ``AnnAssign`` nodes converted to plain ``Assign``.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code  # let compile_restricted report the real error

    changed = False
    new_body: list[ast.stmt] = []

    for node in tree.body:
        result, did_change = _strip_annassign_recursive(node)
        if did_change:
            changed = True
        if result is not None:
            new_body.append(result)

    if not changed:
        return code

    tree.body = new_body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def _strip_annassign_recursive(
    node: ast.stmt,
) -> tuple[ast.stmt | None, bool]:
    """Strip AnnAssign from a node, recursing into function/class bodies."""
    changed = False

    if isinstance(node, ast.AnnAssign):
        if node.value is not None:
            # x: int = 5  →  x = 5
            assign = ast.Assign(
                targets=[node.target],
                value=node.value,
                lineno=node.lineno,
                col_offset=node.col_offset,
            )
            return assign, True
        # Bare annotation (x: int) with no value — remove entirely
        return None, True

    # Recurse into compound statements
    if hasattr(node, "body") and isinstance(node.body, list):
        new_body: list[ast.stmt] = []
        for child in node.body:
            stripped_child, did = _strip_annassign_recursive(child)
            if did:
                changed = True
            if stripped_child is not None:
                new_body.append(stripped_child)
        node.body = new_body

    if hasattr(node, "orelse") and isinstance(node.orelse, list):
        new_orelse: list[ast.stmt] = []
        for child in node.orelse:
            stripped_child, did = _strip_annassign_recursive(child)
            if did:
                changed = True
            if stripped_child is not None:
                new_orelse.append(stripped_child)
        node.orelse = new_orelse

    return node, changed


def _compile_restricted_check(code: str) -> list[str]:
    """Compile *code* with RestrictedPython and return any errors.

    Type annotations (``AnnAssign``) are stripped first because
    RestrictedPython does not support them.

    Returns:
        Empty list on success, otherwise a list of human-readable errors.
    """
    stripped = _strip_type_annotations(code)
    try:
        compile_restricted(stripped, "<generated>", "exec")
        return []
    except SyntaxError as exc:
        return [f"SyntaxError: {exc}"]


def _build_restricted_globals() -> dict[str, Any]:
    """Build the restricted globals dict for in-process RestrictedPython exec.

    Provides the guards that RestrictedPython's rewritten AST expects:
    - ``_getattr_`` – guarded attribute access
    - ``_getiter_`` – guarded iteration
    - ``_getitem_`` – guarded item access
    - ``_unpack_sequence_`` / ``_iter_unpack_sequence_`` – guarded unpacking
    - ``__import__`` – delegated to our import whitelist

    Returns:
        A copy of ``safe_globals`` augmented with the guards above.
    """
    glb: dict[str, Any] = safe_globals.copy()
    glb["_getattr_"] = default_guarded_getattr
    glb["_getiter_"] = iter
    glb["_getitem_"] = lambda obj, key: obj[key]
    glb["_unpack_sequence_"] = guarded_unpack_sequence
    glb["_iter_unpack_sequence_"] = guarded_unpack_sequence

    # Custom __import__ that enforces the same whitelist used pre-flight
    _real_import = __import__

    def _restricted_import(
        name: str,
        glb_: dict[str, Any] | None = None,
        loc_: dict[str, Any] | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> Any:
        if not _is_allowed_module(name):
            raise ImportError(f"Import of {name!r} is not allowed in generated code")
        return _real_import(name, glb_, loc_, fromlist, level)

    builtins_dict: dict[str, Any] = glb["__builtins__"]  # safe_globals always uses a dict
    builtins_dict["__import__"] = _restricted_import
    return glb


def validate_code(code: str) -> bool:
    """Validate that generated code is safe and syntactically correct.

    Checks RestrictedPython compilation, dangerous patterns, and import whitelist.

    Args:
        code: Python code to validate

    Returns:
        True if valid, False otherwise
    """
    # RestrictedPython AST-level check (catches syntax errors too)
    rp_errors = _compile_restricted_check(code)
    if rp_errors:
        logger.debug("RestrictedPython rejected code: %s", rp_errors)
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

    # RestrictedPython AST-level check (fast, in-process)
    rp_errors = _compile_restricted_check(code)
    if rp_errors:
        raise ValueError(f"Code rejected by RestrictedPython: {'; '.join(rp_errors)}")

    # ── Build the wrapper that runs inside the subprocess ─────────────
    # The wrapper uses RestrictedPython to compile AND execute the user
    # code with guarded attribute access, iteration, and a restricted
    # __import__ that enforces the same whitelist.
    #
    # Strip type annotations first — RestrictedPython rejects AnnAssign.
    clean_code = _strip_type_annotations(code)
    wrapper = textwrap.dedent("""\
        import json as _json
        import sys as _sys

        from RestrictedPython import compile_restricted as _compile_restricted
        from RestrictedPython.Eval import default_guarded_getattr as _guarded_getattr
        from RestrictedPython.Guards import guarded_unpack_sequence as _guarded_unpack
        from RestrictedPython.Guards import safe_globals as _safe_globals

        # ── Allowed-import whitelist (serialised from pre-flight set) ──
        _ALLOWED = frozenset({allowed_repr})
        _PREFIXES = {prefixes_repr}
        _real_import = __import__

        def _restricted_import(name, glb=None, loc=None, fromlist=(), level=0):
            if name not in _ALLOWED and not any(name.startswith(p) for p in _PREFIXES):
                raise ImportError(f"Import of {{name!r}} is not allowed")
            return _real_import(name, glb, loc, fromlist, level)

        # ── Build restricted globals ─────────────────────────────────
        _glb = _safe_globals.copy()
        _glb["_getattr_"] = _guarded_getattr
        _glb["_getiter_"] = iter
        _glb["_getitem_"] = lambda obj, key: obj[key]
        _glb["_unpack_sequence_"] = _guarded_unpack
        _glb["_iter_unpack_sequence_"] = _guarded_unpack
        _glb["__builtins__"]["__import__"] = _restricted_import

        # ── Compile with RestrictedPython ────────────────────────────
        _user_code = {user_code_repr}

        try:
            _bytecode = _compile_restricted(_user_code, "<generated>", "exec")
        except SyntaxError as _e:
            print(_json.dumps({{"__error__": f"RestrictedPython compile error: {{_e}}"}}))
            _sys.exit(1)

        # ── Execute in restricted namespace ──────────────────────────
        exec(_bytecode, _glb)

        if "generate_resources" not in _glb:
            print(_json.dumps({{"__error__": "Code must define generate_resources()"}}))
            _sys.exit(1)

        _result = _glb["generate_resources"]()
        if not isinstance(_result, list):
            _result = [_result]
        print(_json.dumps(_result, default=str))
    """).format(
        user_code_repr=repr(clean_code),
        allowed_repr=repr(set(ALLOWED_MODULES)),
        prefixes_repr=repr(ALLOWED_MODULE_PREFIXES),
    )

    # ── Write to a temp file & run in subprocess ────────────────────────
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", prefix="fhir_synth_", delete=False
    )
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
            raise RuntimeError(f"Expected list from generate_resources(), got {type(data).__name__}")

        return data

    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Code execution timed out after {timeout}s — possible infinite loop"
        ) from None
    finally:
        Path(tmp.name).unlink(missing_ok=True)
