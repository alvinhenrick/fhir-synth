"""Main code generation engine."""

import logging
from typing import Any

from fhir_synth.code_generator.executor import (
    execute_code,
    fix_common_imports,
    validate_code,
    validate_imports,
)
from fhir_synth.code_generator.metrics import calculate_code_quality_score
from fhir_synth.code_generator.prompts import (
    SYSTEM_PROMPT,
    build_bundle_code_prompt,
    build_code_prompt,
    build_fix_prompt,
    build_rules_prompt,
)
from fhir_synth.code_generator.utils import extract_code
from fhir_synth.llm import LLMProvider

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Generates Python code for FHIR resource creation from natural language."""

    def __init__(
        self, llm: LLMProvider, max_retries: int = 2, enable_scoring: bool = False
    ) -> None:
        """Initialize code generator with LLM.

        Args:
            llm: LLM provider for code generation
            max_retries: Number of times to retry if generated code fails execution
            enable_scoring: Enable code quality scoring and logging
        """
        self.llm = llm
        self.max_retries = max_retries
        self.enable_scoring = enable_scoring

    def generate_code_from_prompt(self, prompt: str) -> str:
        """Generate Python code from natural language prompt.

        Args:
            prompt: Natural language description of resources to generate

        Returns:
            Generated Python code as string
        """
        user_prompt = build_code_prompt(prompt)
        code = self.llm.generate_text(SYSTEM_PROMPT, user_prompt)
        return extract_code(code)

    def generate_rules_from_prompt(self, prompt: str) -> dict[str, Any]:
        """Generate rule definitions from prompt.

        Args:
            prompt: Natural language description of generation rules

        Returns:
            Dictionary of rule definitions
        """
        user_prompt = build_rules_prompt(prompt)
        result = self.llm.generate_json(SYSTEM_PROMPT, user_prompt)
        return result

    def generate_bundle_code(self, resource_types: list[str], count_per_resource: int = 10) -> str:
        """Generate code for creating a FHIR bundle with multiple resource types.

        Args:
            resource_types: List of FHIR resource types to include (e.g., ["Patient", "Condition"])
            count_per_resource: Number of each resource type to generate

        Returns:
            Generated Python code
        """
        user_prompt = build_bundle_code_prompt(resource_types, count_per_resource)
        code = self.llm.generate_text(SYSTEM_PROMPT, user_prompt)
        return extract_code(code)

    def validate_code(self, code: str) -> bool:
        """Validate that generated code is safe and syntactically correct.

        Args:
            code: Python code to validate

        Returns:
            True if valid, False otherwise
        """
        return validate_code(code)

    def execute_generated_code(self, code: str, timeout: int = 30) -> list[dict[str, Any]]:
        """Execute generated code safely, with self-healing retry on failure.

        If execution fails, the error is sent back to the LLM to produce a
        corrected version. This repeats up to ``max_retries`` times.

        Args:
            code: Generated Python code
            timeout: Timeout in seconds

        Returns:
            List of generated resources
        """
        # Pre-execution validation: check imports before running
        import_errors = validate_imports(code)
        if import_errors:
            # Try auto-fixing common import issues
            fixed_code = fix_common_imports(code)
            fixed_import_errors = validate_imports(fixed_code)

            if not fixed_import_errors:
                # Auto-fix succeeded
                code = fixed_code
            else:
                # Auto-fix didn't work, include errors in first retry
                error_msg = "\n".join(import_errors)
                code = self._retry_with_error(code, f"Import validation failed:\n{error_msg}")

        last_error: Exception | None = None

        for attempt in range(1 + self.max_retries):
            if not validate_code(code):
                last_error = ValueError("Generated code is not valid Python")
                code = self._retry_with_error(code, str(last_error))
                continue

            try:
                resources = execute_code(code, timeout=timeout)

                # Score code qt his
                if self.enable_scoring:
                    metrics = calculate_code_quality_score(code, resources)
                    logger.info(
                        f"Code quality: {metrics['score']:.2f} ({metrics['grade']}) - "
                        f"{len(metrics.get('warnings', []))} warnings"
                    )
                    if metrics.get("warnings"):
                        for warning in metrics["warnings"]:
                            logger.debug(f"  • {warning}")

                return resources
            except ImportError as exc:
                # Import errors get special handling with auto-fix attempt
                last_error = exc
                if attempt < self.max_retries:
                    fixed_code = fix_common_imports(code)
                    if fixed_code != code:
                        code = fixed_code
                    else:
                        code = self._retry_with_error(code, f"ImportError: {exc}")
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    code = self._retry_with_error(code, str(exc))

        # If we got here, all retries failed
        # Build helpful error message
        error_msg = f"Code execution failed after {self.max_retries + 1} attempts: {last_error}"
        if isinstance(last_error, ImportError):
            error_msg += (
                "\n\nSuggestions:\n"
                "  1. Try a more reliable provider: --provider gpt-4\n"
                "  2. Save and inspect the code: --save-code output.py\n"
                "  3. Check import paths in fhir.resources package"
            )

        raise RuntimeError(error_msg) from last_error

    def _retry_with_error(self, code: str, error: str) -> str:
        """Ask the LLM to fix broken generated code.

        Args:
            code: The code that failed
            error: The error message / traceback

        Returns:
            Corrected Python code
        """
        fix_prompt = build_fix_prompt(code, error)
        fixed = self.llm.generate_text(SYSTEM_PROMPT, fix_prompt)
        return extract_code(fixed)

    @staticmethod
    def apply_metadata_to_resources(
        resources: list[dict[str, Any]],
        security: list[dict[str, Any]] | None = None,
        tag: list[dict[str, Any]] | None = None,
        profile: list[str] | None = None,
        source: str | None = None,
    ) -> list[dict[str, Any]]:
        """Apply metadata to a list of resources.

        Args:
            resources: List of FHIR resource dicts
            security: Security labels to add
            tag: Tags to add
            profile: Profile URLs to add
            source: Source system URI

        Returns:
            Modified resources with metadata
        """
        for resource in resources:
            if not any([security, tag, profile, source]):
                continue

            meta = resource.setdefault("meta", {})

            if security:
                existing = meta.get("security", [])
                meta["security"] = existing + security

            if tag:
                existing = meta.get("tag", [])
                meta["tag"] = existing + tag

            if profile:
                existing = meta.get("profile", [])
                meta["profile"] = existing + profile

            if source:
                meta["source"] = source

        return resources
