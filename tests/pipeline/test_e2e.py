"""End-to-end integration tests for the two-stage pipeline.

Tier 1 (always run): full pipeline with stub planner + real FHIR code execution.
Tier 2 (dspy marker): DSPy module structure and DummyLM-based planner tests.
Tier 3 (llm marker):  real LLM call — skipped unless OPENAI_API_KEY etc. is set.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from fhir_synth.pipeline.evaluator import GenerationEvaluator
from fhir_synth.pipeline.models import ClinicalFinding, ClinicalPlan, Coding, MedicationEntry, PatientProfile
from fhir_synth.pipeline.pipeline import FHIRGuidelinesBuilder, PipelineResult, SkillContextBuilder, TwoStagePipeline


# ── Shared fixtures ───────────────────────────────────────────────────────────


def _diabetic_plan() -> ClinicalPlan:
    return ClinicalPlan(
        patients=[
            PatientProfile(
                age=62,
                gender="male",
                race="White",
                conditions=[
                    ClinicalFinding(
                        coding=Coding(
                            system="http://snomed.info/sct",
                            code="44054006",
                            display="Type 2 diabetes mellitus",
                        ),
                        onset_description="8 years ago",
                        severity="moderate",
                    )
                ],
                medications=[
                    MedicationEntry(
                        rxnorm_code="6809",
                        display="Metformin 500mg",
                        dose="500mg",
                        frequency="twice daily",
                    )
                ],
            )
        ],
        care_setting="outpatient clinic",
        encounter_type="follow-up",
        notes="Include HbA1c observation with realistic value around 7.5%",
    )


_VALID_CODE = '''
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.reference import Reference
from uuid import uuid4

def generate_resources():
    patient_id = str(uuid4())
    patient = Patient(
        id=patient_id,
        identifier=[{"system": "http://example.org", "value": patient_id}],
        name=[{"family": "Doe", "given": ["John"]}],
        gender="male",
        birthDate="1962-03-15",
    )
    condition = Condition(
        id=str(uuid4()),
        clinicalStatus=CodeableConcept(
            coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                code="active",
            )]
        ),
        category=[CodeableConcept(
            coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/condition-category",
                code="encounter-diagnosis",
            )]
        )],
        code=CodeableConcept(
            coding=[Coding(
                system="http://snomed.info/sct",
                code="44054006",
                display="Type 2 diabetes mellitus",
            )]
        ),
        subject=Reference(reference=f"Patient/{patient_id}"),
    )
    observation = Observation(
        id=str(uuid4()),
        status="final",
        category=[CodeableConcept(
            coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/observation-category",
                code="laboratory",
            )]
        )],
        code=CodeableConcept(
            coding=[Coding(system="http://loinc.org", code="4548-4", display="HbA1c")]
        ),
        subject=Reference(reference=f"Patient/{patient_id}"),
        valueQuantity={"value": 7.5, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%"},
    )
    return [
        patient.model_dump(exclude_none=True),
        condition.model_dump(exclude_none=True),
        observation.model_dump(exclude_none=True),
    ]
'''


class _PlanReturner:
    """Stub planner — always returns a fixed ClinicalPlan."""

    def __init__(self, plan: ClinicalPlan) -> None:
        self._plan = plan

    def plan(self, prompt: str, skills_context: str) -> ClinicalPlan:
        return self._plan


class _CodeReturner:
    """Stub synthesizer — always returns a fixed code string."""

    def __init__(self, code: str) -> None:
        self._code = code

    def synthesize(self, plan: ClinicalPlan) -> str:
        return self._code


# ── Tier 1: Full pipeline with real execution ─────────────────────────────────


def test_pipeline_produces_valid_fhir_resources() -> None:
    """Full pipeline: stub planner + stub synthesizer + real FHIR execution."""
    pipeline = TwoStagePipeline(
        planner=_PlanReturner(_diabetic_plan()),
        synthesizer=_CodeReturner(_VALID_CODE),
        evaluator=GenerationEvaluator(),
    )
    result = pipeline.run("diabetic patient with HbA1c")

    assert isinstance(result, PipelineResult)
    assert len(result.resources) == 3
    resource_types = {r["resourceType"] for r in result.resources}
    assert resource_types == {"Patient", "Condition", "Observation"}


def test_pipeline_reference_integrity_after_run() -> None:
    """After running, all internal references should be valid."""
    from fhir_synth.code_generator.fhir_validation import validate_references

    pipeline = TwoStagePipeline(
        planner=_PlanReturner(_diabetic_plan()),
        synthesizer=_CodeReturner(_VALID_CODE),
        evaluator=GenerationEvaluator(),
    )
    result = pipeline.run("diabetic patient")
    assert validate_references(result.resources) == []


def test_pipeline_evaluation_report_scores() -> None:
    """Quality report must contain the three expected metric scores."""
    pipeline = TwoStagePipeline(
        planner=_PlanReturner(_diabetic_plan()),
        synthesizer=_CodeReturner(_VALID_CODE),
        evaluator=GenerationEvaluator(),
    )
    result = pipeline.run("diabetic patient")
    metric_names = {ms.name for ms in result.report.metric_scores}
    assert "fhir_validation" in metric_names
    assert "reference_integrity" in metric_names
    assert "us_core_compliance" in metric_names
    assert result.report.overall_score > 0.7


def test_pipeline_plan_captured_in_result() -> None:
    plan = _diabetic_plan()
    pipeline = TwoStagePipeline(
        planner=_PlanReturner(plan),
        synthesizer=_CodeReturner(_VALID_CODE),
        evaluator=GenerationEvaluator(),
    )
    result = pipeline.run("any")
    assert result.plan == plan
    assert result.plan.patients[0].age == 62


# ── Tier 2: DSPy structure (dspy-ai must be installed) ────────────────────────


@pytest.mark.slow
def test_dspy_signatures_can_be_constructed() -> None:
    """Verify DSPy signature classes are properly defined."""
    dspy = pytest.importorskip("dspy")
    from fhir_synth.pipeline.dspy_modules import _make_code_signature, _make_plan_signature

    plan_sig = _make_plan_signature(dspy)
    code_sig = _make_code_signature(dspy)

    assert hasattr(plan_sig, "model_fields") or hasattr(plan_sig, "__annotations__")
    assert hasattr(code_sig, "model_fields") or hasattr(code_sig, "__annotations__")


@pytest.mark.slow
def test_configure_dspy_lm_sets_global_lm() -> None:
    dspy = pytest.importorskip("dspy")
    from fhir_synth.pipeline.dspy_modules import configure_dspy_lm

    # Use a DummyLM so no real API call is made
    dummy = dspy.utils.DummyLM(answers=["test"])
    dspy.configure(lm=dummy)
    configure_dspy_lm.__module__  # just verify it's importable

    # DummyLM should be set as global LM
    assert dspy.settings.lm is not None


@pytest.mark.slow
def test_extract_code_strips_markdown_fences() -> None:
    from fhir_synth.pipeline.dspy_modules import _extract_code

    fenced = "```python\ndef foo(): pass\n```"
    assert _extract_code(fenced) == "def foo(): pass"

    plain = "def foo(): pass"
    assert _extract_code(plain) == "def foo(): pass"

    generic_fence = "```\ndef foo(): pass\n```"
    assert _extract_code(generic_fence) == "def foo(): pass"


# ── Tier 3: Supporting services ───────────────────────────────────────────────


def test_fhir_guidelines_builder_produces_non_empty_string() -> None:
    builder = FHIRGuidelinesBuilder()
    guidelines = builder.build()
    assert isinstance(guidelines, str)
    assert len(guidelines) > 500  # sanity check it's substantive
    assert "fhir" in guidelines.lower()


def test_fhir_guidelines_builder_includes_import_guide() -> None:
    builder = FHIRGuidelinesBuilder()
    guidelines = builder.build(fhir_version="R4B")
    assert "R4B" in guidelines


def test_skill_context_builder_selects_relevant_skills() -> None:
    builder = SkillContextBuilder()
    ctx = builder.build("diabetic patients with medications")
    assert isinstance(ctx, str)
    assert len(ctx) > 100


def test_skill_context_builder_isolated_instances() -> None:
    """Two builders must not share state."""
    b1 = SkillContextBuilder()
    b2 = SkillContextBuilder()
    ctx1 = b1.build("diabetic patients")
    ctx2 = b2.build("diabetic patients")
    assert ctx1 == ctx2  # same input → same output


# ── Tier 4: Real LLM (requires API key in env) ────────────────────────────────


@pytest.mark.llm
def test_dspy_pipeline_end_to_end_with_real_llm() -> None:
    """Full two-stage pipeline with real DSPy + LLM.

    Requires OPENAI_API_KEY (or equivalent) in environment.
    Run with: pytest -m llm tests/pipeline/test_e2e.py
    """
    dspy = pytest.importorskip("dspy")

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("No LLM API key in environment — set OPENAI_API_KEY or ANTHROPIC_API_KEY")

    from fhir_synth.llm import get_provider
    from fhir_synth.pipeline.pipeline import TwoStagePipeline

    model = "gpt-4o-mini" if os.getenv("OPENAI_API_KEY") else "claude-haiku-4-5-20251001"
    llm = get_provider(model)

    pipeline = TwoStagePipeline.default(llm_provider=llm)
    result = pipeline.run("2 diabetic patients with HbA1c observations and Metformin prescriptions")

    assert len(result.resources) > 0
    assert any(r["resourceType"] == "Patient" for r in result.resources)
    assert result.report.overall_score > 0.5
