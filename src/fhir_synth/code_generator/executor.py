"""Code execution and validation utilities."""

import ast
import importlib.util
import re
from typing import Any

from fhir_synth.fhir_spec import class_to_module


def validate_code(code: str) -> bool:
    """Validate that generated code is safe and syntactically correct.

    Args:
        code: Python code to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        compile(code, "<generated>", "exec")
        return True
    except SyntaxError:
        return False


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

                    # Suggest fix using introspected class→module map
                    if node.names:
                        for alias in node.names:
                            correct_mod = class_to_module(alias.name)
                            if correct_mod:
                                errors.append(
                                    f"  → Fix: from fhir.resources.R4B.{correct_mod} import {alias.name}"
                                )

    return errors


def fix_common_imports(code: str) -> str:
    """Auto-fix import mistakes in generated code using introspected class→module map.

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


def execute_code(code: str) -> list[dict[str, Any]]:
    """Run code in a sandboxed namespace and return resources.

    Args:
        code: Python code to execute

    Returns:
        List of generated resources

    Raises:
        ValueError: If code doesn't define generate_resources() function
    """
    safe_globals: dict[str, Any] = {
        "__builtins__": {
            "dict": dict,
            "list": list,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "isinstance": isinstance,
            "print": print,
            "__import__": __import__,
        }
    }

    exec(code, safe_globals)  # noqa: S102

    if "generate_resources" in safe_globals:
        result = safe_globals["generate_resources"]()
        return result if isinstance(result, list) else [result]

    raise ValueError("Generated code must define generate_resources() function")
