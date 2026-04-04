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
    ClinicalFinding,
    ClinicalPlan,
    Coding,
    MedicationEntry,
    PatientProfile,
)
from fhir_synth.pipeline.protocols import ClinicalPlanner, CodeSynthesizer, QualityMetric

__all__ = [
    # Models
    "ClinicalFinding",
    "ClinicalPlan",
    "Coding",
    "MedicationEntry",
    "PatientProfile",
    # Protocols
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
