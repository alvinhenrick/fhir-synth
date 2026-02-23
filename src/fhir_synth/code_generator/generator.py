"""Main code generation engine."""

from typing import Any

from fhir_synth.code_generator.executor import execute_code, validate_code
from fhir_synth.code_generator.prompts import (
    SYSTEM_PROMPT,
    build_bundle_code_prompt,
    build_code_prompt,
    build_fix_prompt,
    build_rules_prompt,
)
from fhir_synth.code_generator.utils import extract_code
from fhir_synth.llm import LLMProvider


class CodeGenerator:
    """Generates Python code for FHIR resource creation from natural language."""

    def __init__(self, llm: LLMProvider, max_retries: int = 2) -> None:
        """Initialize code generator with LLM.

        Args:
            llm: LLM provider for code generation
            max_retries: Number of times to retry if generated code fails execution
        """
        self.llm = llm
        self.max_retries = max_retries

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
        last_error: Exception | None = None

        for attempt in range(1 + self.max_retries):
            if not validate_code(code):
                last_error = ValueError("Generated code is not valid Python")
                code = self._retry_with_error(code, str(last_error))
                continue

            try:
                return execute_code(code)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    code = self._retry_with_error(code, str(exc))

        raise RuntimeError(
            f"Code execution failed after {self.max_retries + 1} attempts: {last_error}"
        ) from last_error

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

