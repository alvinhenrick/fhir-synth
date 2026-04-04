"""Abstract interfaces (protocols) for the two-stage pipeline.

Depend on these abstractions — never on concrete implementations.
All types are runtime-checkable so isinstance() works in tests.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from fhir_synth.pipeline.models import ClinicalPlan


@runtime_checkable
class ClinicalPlanner(Protocol):
    """Converts a natural-language prompt into a structured ClinicalPlan.

    Stage 1 of the pipeline.  Implementations may use DSPy, a raw LLM call,
    or a deterministic stub for testing.
    """

    def plan(self, prompt: str, skills_context: str) -> ClinicalPlan:
        """Produce a ClinicalPlan from a user prompt and clinical skill context.

        Args:
            prompt: Natural-language generation request.
            skills_context: Concatenated clinical skill knowledge relevant to the prompt.

        Returns:
            Validated ClinicalPlan ready for code synthesis.
        """
        ...


@runtime_checkable
class CodeSynthesizer(Protocol):
    """Converts a ClinicalPlan into executable Python code.

    Stage 2 of the pipeline.  The generated code must define a
    ``generate_resources() -> list[dict]`` function.
    """

    def synthesize(self, plan: ClinicalPlan) -> str:
        """Generate Python source code from a clinical plan.

        Args:
            plan: Validated clinical data plan from Stage 1.

        Returns:
            Python source code as a string.
        """
        ...


@runtime_checkable
class QualityMetric(Protocol):
    """Single-concern quality measurement over a list of FHIR resources.

    Implementations are composable: the GenerationEvaluator aggregates
    multiple metrics into a weighted overall score.
    """

    @property
    def name(self) -> str:
        """Unique, human-readable metric identifier."""
        ...

    @property
    def weight(self) -> float:
        """Relative weight for weighted aggregation (must be > 0)."""
        ...

    def score(self, resources: list[dict[str, Any]]) -> float:
        """Compute a quality score for a batch of FHIR resources.

        Args:
            resources: Flat list of FHIR resource dicts.

        Returns:
            Score in the range [0.0, 1.0].  1.0 = perfect.
        """
        ...
