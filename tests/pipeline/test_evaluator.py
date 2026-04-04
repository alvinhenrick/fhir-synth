"""Tests for GenerationEvaluator and QualityMetric implementations — TDD."""

from __future__ import annotations

from typing import Any

import pytest

from fhir_synth.pipeline.evaluator import (
    EvaluationReport,
    FHIRValidationMetric,
    GenerationEvaluator,
    MetricScore,
    ReferenceIntegrityMetric,
    USCoreComplianceMetric,
)
from fhir_synth.pipeline.protocols import QualityMetric


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _valid_patient(pid: str = "p1") -> dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": pid,
        "identifier": [{"system": "http://example.org", "value": pid}],
        "name": [{"family": "Smith", "given": ["John"]}],
        "gender": "male",
        "birthDate": "1970-01-15",
    }


def _condition_for(pid: str, cid: str = "c1") -> dict[str, Any]:
    return {
        "resourceType": "Condition",
        "id": cid,
        "clinicalStatus": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                }
            ]
        },
        "category": [{"coding": [{"code": "encounter-diagnosis"}]}],
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "44054006"}]},
        "subject": {"reference": f"Patient/{pid}"},
    }


# ── FHIRValidationMetric ──────────────────────────────────────────────────────


def test_fhir_metric_perfect_score_on_valid_resources():
    metric = FHIRValidationMetric()
    resources = [_valid_patient(), _condition_for("p1")]
    assert metric.score(resources) == 1.0


def test_fhir_metric_lower_score_on_invalid_resources():
    metric = FHIRValidationMetric()
    resources = [
        _valid_patient(),
        {"resourceType": "Observation", "status": "final"},  # missing code
    ]
    assert metric.score(resources) < 1.0


def test_fhir_metric_zero_on_empty():
    metric = FHIRValidationMetric()
    assert metric.score([]) == 1.0  # nothing to fail


def test_fhir_metric_name_and_weight():
    m = FHIRValidationMetric()
    assert isinstance(m.name, str) and m.name
    assert 0 < m.weight <= 1.0


# ── ReferenceIntegrityMetric ──────────────────────────────────────────────────


def test_ref_metric_perfect_when_all_refs_valid():
    metric = ReferenceIntegrityMetric()
    resources = [_valid_patient("p1"), _condition_for("p1")]
    assert metric.score(resources) == 1.0


def test_ref_metric_lower_on_broken_refs():
    metric = ReferenceIntegrityMetric()
    resources = [
        _valid_patient("p1"),
        {
            "resourceType": "Condition",
            "id": "c1",
            "subject": {"reference": "Patient/nobody"},
        },
    ]
    assert metric.score(resources) < 1.0


def test_ref_metric_name_and_weight():
    m = ReferenceIntegrityMetric()
    assert isinstance(m.name, str) and m.name
    assert 0 < m.weight <= 1.0


# ── USCoreComplianceMetric ────────────────────────────────────────────────────


def test_us_core_metric_perfect_on_compliant_resources():
    metric = USCoreComplianceMetric()
    resources = [_valid_patient()]
    assert metric.score(resources) == 1.0


def test_us_core_metric_lower_on_non_compliant():
    metric = USCoreComplianceMetric()
    resources = [{"resourceType": "Patient", "id": "p1"}]  # missing name, gender, etc.
    assert metric.score(resources) < 1.0


def test_us_core_metric_name_and_weight():
    m = USCoreComplianceMetric()
    assert isinstance(m.name, str) and m.name
    assert 0 < m.weight <= 1.0


# ── QualityMetric protocol satisfaction ──────────────────────────────────────


@pytest.mark.parametrize(
    "metric_cls",
    [FHIRValidationMetric, ReferenceIntegrityMetric, USCoreComplianceMetric],
)
def test_metric_satisfies_protocol(metric_cls: type) -> None:
    assert isinstance(metric_cls(), QualityMetric)


# ── MetricScore ───────────────────────────────────────────────────────────────


def test_metric_score_is_frozen():
    ms = MetricScore(name="test", score=0.9, weight=0.5, details={})
    with pytest.raises(Exception):  # frozen dataclass
        ms.score = 0.5  # type: ignore[misc]


# ── EvaluationReport ─────────────────────────────────────────────────────────


def test_evaluation_report_overall_score():
    report = EvaluationReport(
        metric_scores=[
            MetricScore(name="a", score=1.0, weight=0.5, details={}),
            MetricScore(name="b", score=0.5, weight=0.5, details={}),
        ]
    )
    assert report.overall_score == pytest.approx(0.75)


def test_evaluation_report_grade_a_plus():
    report = EvaluationReport(
        metric_scores=[MetricScore(name="a", score=1.0, weight=1.0, details={})]
    )
    assert report.grade == "A+"


def test_evaluation_report_grade_f():
    report = EvaluationReport(
        metric_scores=[MetricScore(name="a", score=0.5, weight=1.0, details={})]
    )
    assert report.grade == "F"


def test_evaluation_report_as_dict_keys():
    report = EvaluationReport(
        metric_scores=[
            MetricScore(name="fhir", score=0.9, weight=0.4, details={}),
            MetricScore(name="refs", score=1.0, weight=0.6, details={}),
        ]
    )
    d = report.as_dict()
    assert "overall_score" in d
    assert "grade" in d
    assert "metrics" in d
    assert "fhir" in d["metrics"]
    assert "refs" in d["metrics"]


def test_evaluation_report_empty_metrics():
    report = EvaluationReport(metric_scores=[])
    assert report.overall_score == 1.0


# ── GenerationEvaluator ───────────────────────────────────────────────────────


def test_evaluator_default_metrics():
    evaluator = GenerationEvaluator()
    assert len(evaluator.metrics) == 3


def test_evaluator_custom_metrics():
    class ConstantMetric:
        name = "constant"
        weight = 1.0

        def score(self, resources: list[dict[str, Any]]) -> float:
            return 0.8

    evaluator = GenerationEvaluator(metrics=[ConstantMetric()])
    report = evaluator.evaluate([_valid_patient()])
    assert report.overall_score == pytest.approx(0.8)


def test_evaluator_all_perfect():
    evaluator = GenerationEvaluator()
    resources = [_valid_patient("p1"), _condition_for("p1")]
    report = evaluator.evaluate(resources)
    assert report.overall_score == pytest.approx(1.0)
    assert report.grade == "A+"


def test_evaluator_dspy_metric_returns_float():
    evaluator = GenerationEvaluator()
    resources = [_valid_patient("p1")]

    class _Pred:
        pass

    pred = _Pred()
    pred.resources = resources  # type: ignore[attr-defined]
    score = evaluator.dspy_metric(example=None, prediction=pred)
    assert 0.0 <= score <= 1.0


def test_evaluator_dspy_metric_handles_missing_resources():
    evaluator = GenerationEvaluator()
    score = evaluator.dspy_metric(example=None, prediction=object())
    assert score == 0.0
