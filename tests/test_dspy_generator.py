"""Tests for DSPy-powered code generator (ProgramOfThought)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from fhir_synth.code_generator.dspy_generator import (
    DSPyCodeGenerator,
    FHIRInterpreter,
    FHIRResourceGeneration,
    LiteLLMAdapter,
    _build_demos,
    _build_generation_context,
)

_SAMPLE_CODE = (
    "from fhir.resources.R4B.patient import Patient\n"
    "from uuid import uuid4\n"
    "\n"
    "def generate_resources() -> list[dict]:\n"
    "    resources = []\n"
    "    patient = Patient(\n"
    "        id=str(uuid4()),\n"
    '        name=[{"given": ["Test"], "family": "Patient"}],\n'
    '        gender="male",\n'
    '        birthDate="1990-01-01"\n'
    "    )\n"
    "    resources.append(patient.model_dump(exclude_none=True))\n"
    "    return resources"
)

_SAMPLE_RESOURCES = [
    {"resourceType": "Patient", "id": "test-1", "gender": "male", "birthDate": "1990-01-01"}
]


class MockLLMProvider:
    """Mock LLM provider returning DSPy-compatible JSON."""

    def __init__(self, model: str = "mock-gpt") -> None:
        self.model = model
        self.call_count = 0

    def generate_text(
        self, prompt: str, system: str | None = None, json_schema: dict | None = None
    ) -> str:
        self.call_count += 1
        return json.dumps(
            {
                "reasoning": "Create a Patient resource with basic demographics.",
                "resources": json.dumps(_SAMPLE_RESOURCES),
                "code": _SAMPLE_CODE,
            }
        )


# -- LiteLLM Adapter -----------------------------------------------------------


class TestLiteLLMAdapter:
    def test_init(self):
        mock_llm = MockLLMProvider()
        adapter = LiteLLMAdapter(mock_llm)
        assert adapter.provider is mock_llm
        assert adapter.model == "mock-gpt"

    def test_call_with_prompt(self):
        mock_llm = MockLLMProvider()
        adapter = LiteLLMAdapter(mock_llm)
        responses = adapter(prompt="Generate a patient")
        assert len(responses) == 1
        assert mock_llm.call_count == 1

    def test_call_with_messages(self):
        mock_llm = MockLLMProvider()
        adapter = LiteLLMAdapter(mock_llm)
        messages = [
            {"role": "system", "content": "You are a FHIR expert"},
            {"role": "user", "content": "Generate a patient"},
        ]
        responses = adapter(messages=messages)
        assert len(responses) == 1

    def test_call_no_input_raises(self):
        adapter = LiteLLMAdapter(MockLLMProvider())
        with pytest.raises(ValueError, match="Either prompt or messages"):
            adapter()

    def test_inspect_history(self):
        adapter = LiteLLMAdapter(MockLLMProvider())
        adapter(prompt="test")
        history = adapter.inspect_history(n=1)
        assert len(history) == 1
        assert "messages" in history[0]
        assert "response" in history[0]


# -- FHIRInterpreter -----------------------------------------------------------


class TestFHIRInterpreter:
    def test_execute_delegates_to_executor(self):
        mock_executor = MagicMock()
        mock_executor.execute.return_value = MagicMock(artifacts=_SAMPLE_RESOURCES)
        interpreter = FHIRInterpreter(mock_executor, timeout=60)

        result = interpreter.execute("some code")

        mock_executor.execute.assert_called_once_with("some code", timeout=60)
        assert json.loads(result) == _SAMPLE_RESOURCES

    def test_shutdown_is_noop(self):
        interpreter = FHIRInterpreter(MagicMock())
        interpreter.shutdown()  # should not raise


# -- Generator init & config ---------------------------------------------------


class TestDSPyCodeGeneratorInit:
    def test_init_defaults(self):
        gen = DSPyCodeGenerator(MockLLMProvider())
        assert gen.max_retries == 3
        assert gen.enable_scoring is False
        assert gen._context  # context was built

    def test_init_custom_retries(self):
        gen = DSPyCodeGenerator(MockLLMProvider(), max_retries=5)
        assert gen.max_retries == 5

    def test_pot_has_demos(self):
        gen = DSPyCodeGenerator(MockLLMProvider())
        demos = gen.pot.code_generate.demos
        assert len(demos) >= 3
        for demo in demos:
            assert "requirement" in demo
            assert "context" in demo


# -- Few-shot demos ------------------------------------------------------------


class TestFewShotDemos:
    def test_demos_loaded(self):
        ctx = _build_generation_context()
        demos = _build_demos(ctx)
        assert len(demos) >= 3
        for demo in demos:
            assert "requirement" in demo
            assert "context" in demo

    def test_context_contains_all_sections(self):
        ctx = _build_generation_context()
        assert "SANDBOX CONSTRAINTS" in ctx
        assert "IMPORT GUIDE" in ctx
        assert "CLINICAL RULES" in ctx
        assert "FHIR SPEC" in ctx


# -- Signature -----------------------------------------------------------------


class TestSignature:
    def test_signature_fields(self):
        assert "requirement" in FHIRResourceGeneration.input_fields
        assert "context" in FHIRResourceGeneration.input_fields
        assert "resources" in FHIRResourceGeneration.output_fields


# -- execute_generated_code (direct executor path) ----------------------------


class TestExecuteGeneratedCode:
    def test_execute_returns_artifacts(self):
        mock_executor = MagicMock()
        mock_executor.execute.return_value = MagicMock(artifacts=_SAMPLE_RESOURCES)
        gen = DSPyCodeGenerator(MockLLMProvider(), executor=mock_executor)

        result = gen.execute_generated_code("some code", timeout=15)

        assert result == _SAMPLE_RESOURCES
        mock_executor.execute.assert_called_once_with("some code", timeout=15)


# -- Metadata ------------------------------------------------------------------


class TestMetadata:
    def test_metadata_application(self):
        resources = [
            {"resourceType": "Patient", "id": "p1"},
            {"resourceType": "Patient", "id": "p2"},
        ]
        security = [{"system": "http://test.org", "code": "R", "display": "Restricted"}]
        tag = [{"system": "http://example.org", "code": "test"}]
        result = DSPyCodeGenerator.apply_metadata_to_resources(
            resources, security=security, tag=tag, source="http://test.org"
        )
        assert len(result) == 2
        for r in result:
            assert r["meta"]["security"] == security
            assert r["meta"]["tag"] == tag
            assert r["meta"]["source"] == "http://test.org"

    def test_metadata_noop_when_empty(self):
        resources = [{"resourceType": "Patient", "id": "p1"}]
        result = DSPyCodeGenerator.apply_metadata_to_resources(resources)
        assert "meta" not in result[0]

    @pytest.mark.parametrize(
        "kwargs,expected_key",
        [
            (
                {"profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]},
                "profile",
            ),
            ({"source": "http://example.org"}, "source"),
        ],
    )
    def test_metadata_individual_fields(self, kwargs, expected_key):
        resources = [{"resourceType": "Patient", "id": "p1"}]
        result = DSPyCodeGenerator.apply_metadata_to_resources(resources, **kwargs)
        assert expected_key in result[0]["meta"]


# -- Integration (requires API key) -------------------------------------------


@pytest.mark.llm
def test_dspy_pot_with_real_llm():
    """End-to-end: ProgramOfThought generates + executes FHIR code."""
    from fhir_synth.llm import get_provider

    llm = get_provider("gpt-4")
    gen = DSPyCodeGenerator(llm)
    resources = gen.generate("Generate 2 patients with different genders")
    assert len(resources) >= 2
    assert all(r.get("resourceType") == "Patient" for r in resources)
