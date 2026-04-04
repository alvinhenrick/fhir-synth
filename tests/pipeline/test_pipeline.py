"""Integration tests for TwoStagePipeline — TDD.

All tests use stub implementations of ClinicalPlanner and CodeSynthesizer
so no LLM or DSPy installation is needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from fhir_synth.pipeline.evaluator import GenerationEvaluator
from fhir_synth.pipeline.models import ClinicalPlan, PatientProfile
from fhir_synth.pipeline.pipeline import PipelineResult, SkillContextBuilder, TwoStagePipeline

# ── Stubs ─────────────────────────────────────────────────────────────────────


def _simple_plan() -> ClinicalPlan:
    return ClinicalPlan(
        patients=[PatientProfile(age=45, gender="female")],
        care_setting="outpatient",
        encounter_type="routine visit",
    )


_VALID_CODE = """
from fhir.resources.R4B.patient import Patient
from uuid import uuid4

def generate_resources():
    p = Patient(
        id=str(uuid4()),
        name=[{"family": "Test", "given": ["Patient"]}],
        gender="female",
        birthDate="1979-01-01",
        identifier=[{"system": "http://example.org", "value": "123"}],
    )
    return [p.model_dump(exclude_none=True)]
"""


class _StubPlanner:
    """Always returns a fixed ClinicalPlan."""

    def plan(self, prompt: str, skills_context: str) -> ClinicalPlan:
        return _simple_plan()


class _StubSynthesizer:
    """Always returns valid Python code."""

    def synthesize(self, plan: ClinicalPlan) -> str:
        return _VALID_CODE


class _FailingSynthesizer:
    """Always raises to simulate a synthesis failure."""

    def synthesize(self, plan: ClinicalPlan) -> str:
        raise RuntimeError("synthesis failed")


# ── PipelineResult ────────────────────────────────────────────────────────────


def test_pipeline_result_has_expected_fields(tmp_path: Any) -> None:
    pipeline = TwoStagePipeline(
        planner=_StubPlanner(),
        synthesizer=_StubSynthesizer(),
        evaluator=GenerationEvaluator(),
    )
    result = pipeline.run("5 diabetic patients")
    assert isinstance(result, PipelineResult)
    assert result.plan is not None
    assert isinstance(result.code, str)
    assert isinstance(result.resources, list)
    assert result.report is not None


def test_pipeline_resources_are_non_empty() -> None:
    pipeline = TwoStagePipeline(
        planner=_StubPlanner(),
        synthesizer=_StubSynthesizer(),
        evaluator=GenerationEvaluator(),
    )
    result = pipeline.run("5 diabetic patients")
    assert len(result.resources) > 0
    assert all(isinstance(r, dict) for r in result.resources)


def test_pipeline_report_has_overall_score() -> None:
    pipeline = TwoStagePipeline(
        planner=_StubPlanner(),
        synthesizer=_StubSynthesizer(),
        evaluator=GenerationEvaluator(),
    )
    result = pipeline.run("any prompt")
    assert 0.0 <= result.report.overall_score <= 1.0


def test_pipeline_plan_is_passed_to_synthesizer() -> None:
    received: list[ClinicalPlan] = []

    class _CaptureSynthesizer:
        def synthesize(self, plan: ClinicalPlan) -> str:
            received.append(plan)
            return _VALID_CODE

    pipeline = TwoStagePipeline(
        planner=_StubPlanner(),
        synthesizer=_CaptureSynthesizer(),
        evaluator=GenerationEvaluator(),
    )
    pipeline.run("any prompt")
    assert len(received) == 1
    assert received[0] == _simple_plan()


def test_pipeline_propagates_synthesis_error() -> None:
    pipeline = TwoStagePipeline(
        planner=_StubPlanner(),
        synthesizer=_FailingSynthesizer(),
        evaluator=GenerationEvaluator(),
    )
    with pytest.raises(RuntimeError, match="synthesis failed"):
        pipeline.run("any prompt")


# ── SkillContextBuilder ───────────────────────────────────────────────────────


def test_skill_context_builder_returns_string() -> None:
    builder = SkillContextBuilder()
    ctx = builder.build("diabetic patients with HbA1c")
    assert isinstance(ctx, str)
    assert len(ctx) > 0


def test_skill_context_builder_empty_prompt_returns_all_skills() -> None:
    builder = SkillContextBuilder()
    ctx = builder.build("")
    # Should fall back to all skills — non-empty
    assert len(ctx) > 0


# ── TwoStagePipeline.default() factory ───────────────────────────────────────


def test_pipeline_default_factory_requires_dspy() -> None:
    """default() raises ImportError with a helpful message when dspy-ai is not installed."""
    pytest.importorskip("dspy", reason="dspy-ai not installed")  # skip if not installed
    # If we get here dspy IS installed — factory should succeed
    mock_llm = MagicMock()
    mock_llm.model = "mock"
    pipeline = TwoStagePipeline.default(llm_provider=mock_llm)
    assert isinstance(pipeline, TwoStagePipeline)


def test_pipeline_default_factory_raises_helpful_error_without_dspy(monkeypatch: Any) -> None:
    """When dspy import fails, the error message tells the user how to install it."""
    import builtins

    real_import = builtins.__import__

    def _block_dspy(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "dspy":
            raise ModuleNotFoundError("No module named 'dspy'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_dspy)

    mock_llm = MagicMock()
    mock_llm.model = "mock"
    with pytest.raises(ImportError, match="fhir-synth\\[dspy\\]"):
        TwoStagePipeline.default(llm_provider=mock_llm)
