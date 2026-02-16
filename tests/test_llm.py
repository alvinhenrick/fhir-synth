"""Tests for LLM providers."""

from fhir_synth.llm import MockLLMProvider, get_provider


def test_mock_llm_provider_generate_json():
    """Mock provider should return parsed JSON and record calls."""
    llm = MockLLMProvider(response='{"test": "value"}')
    result = llm.generate_json("test prompt")

    assert result == {"test": "value"}
    assert len(llm.calls) == 1
    assert llm.calls[0]["prompt"] == "test prompt"


def test_get_provider_mock():
    """get_provider should return a MockLLMProvider for 'mock'."""
    llm = get_provider("mock")
    assert isinstance(llm, MockLLMProvider)
