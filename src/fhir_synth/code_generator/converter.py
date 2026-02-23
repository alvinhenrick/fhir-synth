"""Prompt to rules converter."""

from typing import Any

from fhir_synth.code_generator.constants import SUPPORTED_RESOURCE_TYPES
from fhir_synth.code_generator.generator import CodeGenerator
from fhir_synth.llm import LLMProvider


class PromptToRulesConverter:
    """Convert natural language prompts to declarative rules."""

    def __init__(self, llm: LLMProvider) -> None:
        """Initialize converter.

        Args:
            llm: LLM provider for conversion
        """
        self.llm = llm
        self.code_gen = CodeGenerator(llm)

    def convert_prompt_to_rules(self, prompt: str) -> dict[str, Any]:
        """Convert a prompt to generation rules.

        Args:
            prompt: User prompt describing data to generate

        Returns:
            Dictionary of rules
        """
        return self.code_gen.generate_rules_from_prompt(prompt)

    def convert_prompt_to_code(self, prompt: str) -> str:
        """Convert a prompt to executable Python code.

        Args:
            prompt: User prompt describing data to generate

        Returns:
            Generated Python code
        """
        return self.code_gen.generate_code_from_prompt(prompt)

    def extract_resource_types(self, prompt: str) -> list[str]:
        """Extract FHIR resource types mentioned in prompt.

        Args:
            prompt: User prompt

        Returns:
            List of resource types
        """
        prompt_lower = prompt.lower()
        found = [rt for rt in SUPPORTED_RESOURCE_TYPES if rt.lower() in prompt_lower]

        # Default to Patient if none found
        return found or ["Patient"]

