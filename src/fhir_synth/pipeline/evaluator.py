"""Composable quality metrics and generation evaluator.

Each QualityMetric measures one concern.  GenerationEvaluator aggregates
them into a single weighted EvaluationReport.

The overall_score is what DSPy uses as its optimization target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fhir_synth.code_generator.fhir_validation import validate_references, validate_resources
from fhir_synth.code_generator.us_core_validation import validate_us_core


# ── Value objects ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MetricScore:
    """Immutable result of a single QualityMetric evaluation."""

    name: str
    score: float  # 0.0 – 1.0
    weight: float
    details: dict[str, Any]


@dataclass(frozen=True)
class EvaluationReport:
    """Aggregated quality report across all metrics."""

    metric_scores: list[MetricScore]

    @property
    def overall_score(self) -> float:
        """Weighted average across all metric scores."""
        if not self.metric_scores:
            return 1.0
        total_weight = sum(ms.weight for ms in self.metric_scores)
        if total_weight == 0:
            return 1.0
        return sum(ms.score * ms.weight for ms in self.metric_scores) / total_weight

    @property
    def grade(self) -> str:
        s = self.overall_score
        if s >= 0.95:
            return "A+"
        if s >= 0.90:
            return "A"
        if s >= 0.85:
            return "B+"
        if s >= 0.80:
            return "B"
        if s >= 0.70:
            return "C"
        return "F"

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 4),
            "grade": self.grade,
            "metrics": {ms.name: {"score": round(ms.score, 4), **ms.details} for ms in self.metric_scores},
        }


# ── Concrete metrics ──────────────────────────────────────────────────────────


class FHIRValidationMetric:
    """Pydantic model validation: required fields, types, cardinality."""

    name: str = "fhir_validation"
    weight: float = 0.40

    def score(self, resources: list[dict[str, Any]]) -> float:
        if not resources:
            return 1.0
        vr = validate_resources(resources)
        return vr.pass_rate


class ReferenceIntegrityMetric:
    """All internal FHIR References point to an existing resource in the batch."""

    name: str = "reference_integrity"
    weight: float = 0.35

    def score(self, resources: list[dict[str, Any]]) -> float:
        if not resources:
            return 1.0
        ref_errors = validate_references(resources)
        if not ref_errors:
            return 1.0
        broken = sum(len(e.get("errors", [])) for e in ref_errors)
        # Count total reference fields as a proxy for denominator
        # Penalise proportionally: each broken ref reduces score
        penalty_per_ref = 0.10
        return max(0.0, 1.0 - broken * penalty_per_ref)


class USCoreComplianceMetric:
    """US Core R4 must-support field coverage."""

    name: str = "us_core_compliance"
    weight: float = 0.25

    def score(self, resources: list[dict[str, Any]]) -> float:
        ucr = validate_us_core(resources)
        return ucr.compliance_rate


# ── Evaluator ─────────────────────────────────────────────────────────────────


class GenerationEvaluator:
    """Aggregates QualityMetric instances into a weighted EvaluationReport.

    Designed to be the DSPy optimization target: pass
    ``evaluator.dspy_metric`` directly to ``dspy.Evaluate`` or
    ``dspy.BootstrapFewShot``.
    """

    def __init__(self, metrics: list[Any] | None = None) -> None:
        self.metrics: list[Any] = metrics or [
            FHIRValidationMetric(),
            ReferenceIntegrityMetric(),
            USCoreComplianceMetric(),
        ]

    def evaluate(self, resources: list[dict[str, Any]]) -> EvaluationReport:
        """Score *resources* against every registered metric.

        Args:
            resources: Flat list of FHIR resource dicts.

        Returns:
            EvaluationReport with per-metric and overall scores.
        """
        scores = [
            MetricScore(
                name=m.name,
                score=m.score(resources),
                weight=m.weight,
                details={},
            )
            for m in self.metrics
        ]
        return EvaluationReport(metric_scores=scores)

    def dspy_metric(self, example: Any, prediction: Any, trace: Any = None) -> float:
        """DSPy-compatible metric function.

        DSPy calls this as ``metric(example, prediction, trace)``.
        We extract ``prediction.resources`` and return the overall score.
        """
        resources: list[dict[str, Any]] = getattr(prediction, "resources", None) or []
        if not resources:
            return 0.0  # penalise the optimizer for producing no resources
        return self.evaluate(resources).overall_score
