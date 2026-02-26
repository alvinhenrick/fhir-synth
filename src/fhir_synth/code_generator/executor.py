"""Code execution and validation utilities."""

import ast
import importlib.util
import re
from typing import Any


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

                    # Suggest fix for common mistakes
                    if "." in module:
                        parts = module.split(".")
                        # Check if it's a case issue (e.g., timingrepeat vs timing)
                        if len(parts) >= 4:
                            possible_fix = ".".join(parts[:-1])
                            if importlib.util.find_spec(possible_fix):
                                errors.append(
                                    f"  → Try: from {possible_fix} import {parts[-1].title()}"
                                )

    return errors


def fix_common_imports(code: str) -> str:
    """Auto-fix common import mistakes in generated code.

    Args:
        code: Python code with potential import issues

    Returns:
        Fixed code
    """
    # Common patterns: fhir.resources.R4B.{lowercase_single_word} should sometimes be split
    # e.g., timingrepeat → timing (import TimingRepeat)

    # Pattern: from fhir.resources.R4B.xxxyyy import XxxYyy
    # Should be: from fhir.resources.R4B.xxx import XxxYyy

    common_fixes = {
        r"from fhir\.resources\.R4B\.timingrepeat import": "from fhir.resources.R4B.timing import",
        r"from fhir\.resources\.R4B\.codeableconcept import": "from fhir.resources.R4B.codeableconcept import",
        r"from fhir\.resources\.R4B\.humanname import": "from fhir.resources.R4B.humanname import",
    }

    fixed_code = code
    for pattern, replacement in common_fixes.items():
        fixed_code = re.sub(pattern, replacement, fixed_code)

    return fixed_code


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
