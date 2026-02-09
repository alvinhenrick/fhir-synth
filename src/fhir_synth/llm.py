"""LLM provider interface and prompt-to-plan conversion using LiteLLM."""

from __future__ import annotations

import json
import os
from typing import Any

from fhir_synth.plan import DatasetPlan


class LLMProvider:
    """LLM provider using LiteLLM for unified access to 100+ LLM providers."""

    def __init__(
        self,
        model: str = "gpt-4",
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize LLM provider with LiteLLM.

        Args:
            model: Model name (e.g., "gpt-4", "claude-3-opus", "bedrock/anthropic.claude-v2")
            api_key: API key for the provider (optional, will use env vars)
            api_base: Custom API base URL (optional)
            **kwargs: Additional arguments passed to litellm.completion()
        """
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.extra_kwargs = kwargs

    def generate_text(
        self, prompt: str, system: str | None = None, json_schema: dict[str, Any] | None = None
    ) -> str:
        """Generate text from prompt using LiteLLM."""
        import litellm

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **self.extra_kwargs,
        }

        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        # Request JSON mode if schema provided and model supports it
        if json_schema:
            kwargs["response_format"] = {"type": "json_object"}

        response = litellm.completion(**kwargs)
        return response.choices[0].message.content or ""

    def generate_json(
        self, prompt: str, system: str | None = None, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Generate JSON from prompt."""
        text = self.generate_text(prompt, system, schema)

        # Try to extract JSON from Markdown code blocks if present
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()

        return json.loads(text)  # type: ignore[no-any-return]


class MockLLMProvider:
    """Mock LLM provider for testing (no LiteLLM dependency)."""

    def __init__(self, response: str | dict[str, Any] | None = None) -> None:
        """Initialize with an optional fixed response."""
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def generate_text(
        self, prompt: str, system: str | None = None, json_schema: dict[str, Any] | None = None
    ) -> str:
        """Generate mock text response."""
        self.calls.append({"prompt": prompt, "system": system, "schema": json_schema})

        if isinstance(self.response, str):
            return self.response
        elif isinstance(self.response, dict):
            return json.dumps(self.response)
        else:
            # Return minimal valid plan
            return """{
                "version": 1,
                "seed": 42,
                "population": {"persons": 10},
                "time": {"horizon": {"years": 1}, "timezone": "UTC"}
            }"""

    def generate_json(
        self, prompt: str, system: str | None = None, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Generate a mock JSON response."""
        text = self.generate_text(prompt, system, schema)
        return json.loads(text)  # type: ignore[no-any-return]


def get_provider(
    provider_name: str = "gpt-4", api_key: str | None = None, **kwargs: Any
) -> LLMProvider | MockLLMProvider:
    """Get LLM provider.

    Args:
        provider_name: Provider/model name. Use "mock" for testing, or any LiteLLM-supported model:
            - OpenAI: "gpt-4", "gpt-3.5-turbo"
            - Anthropic: "claude-3-opus-20240229", "claude-3-sonnet-20240229"
            - Bedrock: "bedrock/anthropic.claude-v2", "bedrock/anthropic.claude-instant-v1"
            - Azure: "azure/gpt-4"
            - And 100+ more providers
        api_key: API key (optional, will use environment variables from .env or system)
        **kwargs: Additional arguments

    Returns:
        LLMProvider instance
    """
    if provider_name == "mock":
        return MockLLMProvider(**kwargs)

    # If no api_key provided, check environment for common API key names
    if not api_key:
        # Map provider names to environment variable names
        env_key_map = {
            "gpt-4": "OPENAI_API_KEY",
            "gpt-3.5-turbo": "OPENAI_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "claude-3-opus": "ANTHROPIC_API_KEY",
            "claude-3-sonnet": "ANTHROPIC_API_KEY",
        }

        # Check for matching environment variable
        for provider_prefix, env_var in env_key_map.items():
            if provider_name.startswith(provider_prefix):
                api_key = os.getenv(env_var)
                if api_key:
                    break

    return LLMProvider(model=provider_name, api_key=api_key, **kwargs)


def prompt_to_plan(llm: LLMProvider | MockLLMProvider, prompt: str) -> DatasetPlan:
    """Convert user prompt to validated DatasetPlan."""
    system_prompt = """You are a helpful assistant that converts user prompts into FHIR synthetic data generation plans.

The user will describe what kind of synthetic healthcare data they want to generate. Your job is to convert this into a structured JSON configuration following the DatasetPlan schema.

Guidelines:
- Default to reasonable values if not specified (e.g., 50 persons, 3 years horizon)
- If the user mentions multiple healthcare organizations/systems, use the multi-org "sources" format
- If the user mentions specific conditions or scenarios, add them to the scenarios list
- Always include comprehensive resource types unless the user asks for specific ones
- Clamp large numbers to reasonable limits (max 1000 persons)

Return ONLY valid JSON matching the DatasetPlan schema. Do not include explanations."""

    try:
        plan_dict = llm.generate_json(prompt, system=system_prompt)
    except Exception:
        # Fallback to text extraction
        text = llm.generate_text(prompt, system=system_prompt)
        plan_dict = json.loads(text)

    # Validate and normalize
    plan = DatasetPlan.model_validate(plan_dict)

    # Apply guardrails
    if plan.population.persons > 1000:
        plan.population.persons = 1000

    return plan
