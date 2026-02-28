"""Code quality assessment and metrics for generated code."""

import ast
from typing import Any


def calculate_code_quality_score(
    code: str, resources: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Calculate the quality score for generated code.

    Args:
        code: Generated Python code
        resources: Generated resources (optional, for deeper validation)

    Returns:
        Dictionary with score (0.0-1.0) and detailed metrics
    """
    metrics: dict[str, Any] = {
        "score": 1.0,
        "checks": {},
        "warnings": [],
        "passed": True,
    }

    # Check 1: Has uuid4 import
    if "uuid4" in code or "from uuid import" in code:
        metrics["checks"]["uses_uuid"] = True
    else:
        metrics["checks"]["uses_uuid"] = False
        metrics["score"] -= 0.15
        metrics["warnings"].append("Missing uuid4 for ID generation")

    # Check 2: Has model_dump with exclude_none
    if "model_dump(exclude_none=True)" in code:
        metrics["checks"]["uses_model_dump"] = True
    elif "model_dump(" in code:
        metrics["checks"]["uses_model_dump"] = "partial"
        metrics["score"] -= 0.05
        metrics["warnings"].append("model_dump() should use exclude_none=True")
    else:
        metrics["checks"]["uses_model_dump"] = False
        metrics["score"] -= 0.2
        metrics["warnings"].append("Missing .model_dump(exclude_none=True)")

    # Check 3: Has generate_resources function
    try:
        tree = ast.parse(code)
        has_func = any(
            isinstance(node, ast.FunctionDef) and node.name == "generate_resources"
            for node in ast.walk(tree)
        )
        metrics["checks"]["has_function"] = has_func
        if not has_func:
            metrics["score"] -= 0.3
            metrics["warnings"].append("Missing generate_resources() function")
    except SyntaxError:
        metrics["checks"]["has_function"] = False
        metrics["score"] -= 0.5
        metrics["warnings"].append("Syntax error in code")

    # Check 4: Imports from fhir.resources.R4B
    if "from fhir.resources.R4B" in code:
        metrics["checks"]["uses_fhir_r4b"] = True
    else:
        metrics["checks"]["uses_fhir_r4b"] = False
        metrics["score"] -= 0.1
        metrics["warnings"].append("Should import from fhir.resources.R4B")

    # Check 5: Avoid common bad patterns
    if "from fhir.resources.R4B.timingrepeat import" in code:
        metrics["checks"]["no_bad_imports"] = False
        metrics["score"] -= 0.2
        metrics["warnings"].append("Bad import: timingrepeat module doesn't exist")
    else:
        metrics["checks"]["no_bad_imports"] = True

    # Check 6: If resources provided, validate structure
    if resources:
        patients = [r for r in resources if r.get("resourceType") == "Patient"]
        clinical = [
            r
            for r in resources
            if r.get("resourceType")
            in ["Condition", "Observation", "MedicationRequest", "Procedure"]
        ]

        metrics["checks"]["has_patients"] = len(patients) > 0
        if len(patients) == 0 and len(clinical) > 0:
            metrics["score"] -= 0.2
            metrics["warnings"].append("Clinical resources without Patient resources")

        # Check references
        if clinical and patients:
            has_refs = any("subject" in r or "patient" in r for r in clinical)
            metrics["checks"]["has_references"] = has_refs
            if not has_refs:
                metrics["score"] -= 0.2
                metrics["warnings"].append("Clinical resources don't reference patients")

    # Final scoring
    metrics["score"] = max(0.0, min(1.0, metrics["score"]))
    metrics["passed"] = metrics["score"] >= 0.7
    metrics["grade"] = _get_grade(metrics["score"])

    return metrics


def _get_grade(score: float) -> str:
    """Convert score to letter grade."""
    if score >= 0.95:
        return "A+"
    elif score >= 0.90:
        return "A"
    elif score >= 0.85:
        return "B+"
    elif score >= 0.80:
        return "B"
    elif score >= 0.70:
        return "C"
    else:
        return "F"


def print_quality_report(metrics: dict[str, Any]) -> None:
    """Print a formatted quality report.

    Args:
        metrics: Metrics from calculate_code_quality_score()
    """
    print(f"\n📊 Code Quality Report")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Score: {metrics['score']:.2f} / 1.00 ({metrics['grade']})")
    print(f"Status: {'✅ PASSED' if metrics['passed'] else '❌ FAILED'}")

    if metrics["warnings"]:
        print(f"\n⚠️  Warnings ({len(metrics['warnings'])}):")
        for warning in metrics["warnings"]:
            print(f"  • {warning}")

    print("\n✓ Checks:")
    for check, result in metrics["checks"].items():
        status = "✅" if result is True else "⚠️" if result == "partial" else "❌"
        print(f"  {status} {check.replace('_', ' ').title()}: {result}")
    print()
