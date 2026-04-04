"""Two-stage clinical planning pipeline for FHIR synthetic data generation.

Stage 1 — Clinical Planning:
    Natural language prompt + clinical skills → structured ClinicalPlan

Stage 2 — Code Synthesis:
    ClinicalPlan + FHIR guidelines → Python code → FHIR resources

Evaluation runs after Stage 2 using composable QualityMetric implementations.
"""

from fhir_synth.pipeline.evaluator import (
    EvaluationReport,
    FHIRValidationMetric,
    GenerationEvaluator,
    MetricScore,
    ReferenceIntegrityMetric,
    USCoreComplianceMetric,
)
from fhir_synth.pipeline.models import (
    CareTeamMember,
    ClinicalFinding,
    ClinicalPlan,
    Coding,
    MedicationEntry,
    PatientProfile,
)
from fhir_synth.pipeline.plan_enricher import PlanEnricher
from fhir_synth.pipeline.protocols import ClinicalPlanEnricher, ClinicalPlanner, CodeSynthesizer, QualityMetric

__all__ = [
    # Models
    "CareTeamMember",
    "ClinicalFinding",
    "ClinicalPlan",
    "Coding",
    "MedicationEntry",
    "PatientProfile",
    # Enricher
    "PlanEnricher",
    # Protocols
    "ClinicalPlanEnricher",
    "ClinicalPlanner",
    "CodeSynthesizer",
    "QualityMetric",
    # Evaluator
    "EvaluationReport",
    "FHIRValidationMetric",
    "GenerationEvaluator",
    "MetricScore",
    "ReferenceIntegrityMetric",
    "USCoreComplianceMetric",
]
