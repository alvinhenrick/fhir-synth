"""Prompt to rules converter."""

from typing import Any

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

