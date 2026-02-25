"""Code execution and validation utilities."""

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
