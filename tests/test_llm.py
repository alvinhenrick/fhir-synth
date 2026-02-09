"""Tests for LLM providers."""

from fhir_synth.llm import MockLLMProvider, prompt_to_plan


def test_mock_llm_provider():
    """Test mock LLM provider."""
    llm = MockLLMProvider(response='{"test": "value"}')
    result = llm.generate_json("test prompt")

    assert result == {"test": "value"}
    assert len(llm.calls) == 1
    assert llm.calls[0]["prompt"] == "test prompt"


def test_prompt_to_plan_basic():
    """Test converting prompt to plan."""
    llm = MockLLMProvider(
        response={
            "version": 1,
            "seed": 42,
            "population": {"persons": 20},
            "time": {"horizon": {"years": 2}, "timezone": "UTC"},
        }
    )

    plan = prompt_to_plan(llm, "Generate 20 patients over 2 years")

    assert plan.population.persons == 20
    assert plan.time.horizon.years == 2


def test_prompt_to_plan_guardrails():
    """Test that guardrails are applied."""
    llm = MockLLMProvider(
        response={
            "version": 1,
            "seed": 42,
            "population": {"persons": 5000},  # Too large
            "time": {"horizon": {"years": 1}, "timezone": "UTC"},
        }
    )

    plan = prompt_to_plan(llm, "Generate 5000 patients")

    # Should be clamped to 1000
    assert plan.population.persons == 1000
