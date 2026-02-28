"""LLM provider interface and prompt-to-plan conversion using LiteLLM."""

import json
import os
from typing import Any


class LLMProvider:
    """LLM provider using LiteLLM for unified access to 100+ LLM providers."""

    def __init__(
        self,
        model: str = "gpt-4",
        api_key: str | None = None,
        api_base: str | None = None,
        aws_profile_name: str | None = None,
        aws_region_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize LLM provider with LiteLLM.

        Args:
            model: Model name (e.g., "gpt-4", "claude-3-opus", "bedrock/anthropic.claude-v2")
            api_key: API key for the provider (optional, will use env vars)
            api_base: Custom API base URL (optional)
            aws_profile_name: AWS profile name for Bedrock (optional, uses ~/.aws/credentials)
            aws_region_name: AWS region for Bedrock (optional, e.g., "us-east-1")
            **kwargs: Additional arguments passed to litellm.completion()
        """
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.aws_profile_name = aws_profile_name
        self.aws_region_name = aws_region_name
        self.extra_kwargs = kwargs

    def _is_bedrock(self) -> bool:
        """Check if using AWS Bedrock provider."""
        return self.model.startswith("bedrock/")

    def _get_boto3_session_kwargs(self) -> dict[str, Any]:
        """Build boto3 session kwargs for Bedrock authentication.

        Returns:
            Dictionary with aws_* keys for litellm Bedrock calls
        """
        kwargs: dict[str, Any] = {}

        # Profile name (from constructor, env var, or default)
        profile = self.aws_profile_name or os.getenv("AWS_PROFILE")
        region = self.aws_region_name or os.getenv("AWS_REGION_NAME") or os.getenv("AWS_DEFAULT_REGION")

        if profile or region:
            import boto3

            session_kwargs: dict[str, str] = {}
            if profile:
                session_kwargs["profile_name"] = profile
            if region:
                session_kwargs["region_name"] = region

            session = boto3.Session(**session_kwargs)
            credentials = session.get_credentials()

            if credentials:
                frozen = credentials.get_frozen_credentials()
                kwargs["aws_access_key_id"] = frozen.access_key
                kwargs["aws_secret_access_key"] = frozen.secret_key
                if frozen.token:
                    kwargs["aws_session_token"] = frozen.token

            if region or session.region_name:
                kwargs["aws_region_name"] = region or session.region_name

        return kwargs

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

        # Add AWS Bedrock credentials if applicable
        if self._is_bedrock():
            kwargs.update(self._get_boto3_session_kwargs())

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


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing (no LiteLLM dependency)."""

    def __init__(self, response: str | dict[str, Any] | None = None) -> None:
        """Initialize with an optional fixed response."""
        super().__init__(model="mock")
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
            # Default mock: return Python code that generates sample resources.
            # This allows `fhir-synth generate --provider mock` to work end-to-end.
            return """
from fhir.resources.R4B import patient as patient_mod

def generate_resources():
    resources = []
    for i in range(1, 6):
        p = patient_mod.Patient(
            id=f"mock-patient-{i}",
            name=[{"given": [f"Mock{i}"], "family": "Patient"}],
            gender="unknown",
            birthDate=f"199{i}-01-01",
        )
        resources.append(p.model_dump())
    return resources
"""

    def generate_json(
        self, prompt: str, system: str | None = None, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Generate a mock JSON response."""
        text = self.generate_text(prompt, system, schema)
        return json.loads(text)  # type: ignore[no-any-return]


def get_provider(
    provider_name: str = "gpt-4",
    api_key: str | None = None,
    aws_profile: str | None = None,
    aws_region: str | None = None,
    **kwargs: Any,
) -> LLMProvider:
    """Get LLM provider.

    Args:
        provider_name: Provider/model name. Use "mock" for testing, or any LiteLLM-supported model:
            - OpenAI: "gpt-4", "gpt-4o", "gpt-3.5-turbo"
            - Anthropic: "claude-3-opus-20240229", "claude-3-sonnet-20240229"
            - Bedrock: "bedrock/anthropic.claude-v2",
              "bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0"
            - Azure: "azure/gpt-4"
            - And 100+ more providers via LiteLLM
        api_key: API key (optional, will use environment variables from .env or system)
        aws_profile: AWS profile name for Bedrock (reads ~/.aws/credentials).
            Falls back to ``AWS_PROFILE`` env var.
        aws_region: AWS region for Bedrock (e.g. "us-east-1").
            Falls back to ``AWS_REGION_NAME`` / ``AWS_DEFAULT_REGION`` env vars.
        **kwargs: Additional arguments passed to ``litellm.completion()``

    Returns:
        LLMProvider instance
    """
    if provider_name == "mock":
        return MockLLMProvider(**kwargs)

    # If no api_key provided, check environment for common API key names
    if not api_key:
        env_key_map = {
            "gpt-": "OPENAI_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }

        for provider_prefix, env_var in env_key_map.items():
            if provider_name.startswith(provider_prefix):
                api_key = os.getenv(env_var)
                if api_key:
                    break

    return LLMProvider(
        model=provider_name,
        api_key=api_key,
        aws_profile_name=aws_profile,
        aws_region_name=aws_region,
        **kwargs,
    )
