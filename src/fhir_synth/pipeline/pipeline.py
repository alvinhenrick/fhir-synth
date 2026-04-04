"""TwoStagePipeline: orchestrates clinical planning → code synthesis → execution → evaluation.

Follows the Dependency Inversion principle: this class depends on the
ClinicalPlanner, CodeSynthesizer, and GenerationEvaluator abstractions,
not on DSPy or any specific LLM implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fhir_synth.code_generator.executor import Executor, LocalSmolagentsExecutor
from fhir_synth.code_generator.executor import validate_code, validate_imports, fix_common_imports
from fhir_synth.code_generator.fhir_validation import repair_references
from fhir_synth.code_generator.prompts.loader import load_section, render
from fhir_synth.code_generator.constants import ALLOWED_MODULE_PREFIXES, ALLOWED_MODULES
from fhir_synth.fhir_spec import get_fhir_version, import_guide, spec_summary
from fhir_synth.pipeline.evaluator import EvaluationReport, GenerationEvaluator
from fhir_synth.pipeline.models import ClinicalPlan
from fhir_synth.pipeline.plan_enricher import PlanEnricher
from fhir_synth.pipeline.protocols import ClinicalPlanEnricher, ClinicalPlanner, CodeSynthesizer
from fhir_synth.skills import KeywordSelector, SkillLoader, SkillSelector

logger = logging.getLogger(__name__)

_ALLOWED_LIST = ", ".join(sorted(ALLOWED_MODULES))
_ALLOWED_PREFIXES = ", ".join(f"{p}.*" for p in ALLOWED_MODULE_PREFIXES)


# ── Value objects ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PipelineResult:
    """Immutable result of a single TwoStagePipeline.run() call."""

    plan: ClinicalPlan
    code: str
    resources: list[dict[str, Any]]
    report: EvaluationReport
    repair_report: dict[str, Any] = field(default_factory=dict)


# ── Supporting services ───────────────────────────────────────────────────────


class SkillContextBuilder:
    """Builds the clinical context string injected into Stage 1.

    Uses the existing skill loading infrastructure but returns only the
    clinical Markdown bodies — no FHIR code rules, no sandbox constraints.
    """

    def __init__(
        self,
        user_dirs: list[Path] | None = None,
        selector: SkillSelector | None = None,
    ) -> None:
        self._loader = SkillLoader(user_dirs=user_dirs)
        self._selector: SkillSelector = selector or KeywordSelector()

    def build(self, prompt: str) -> str:
        """Return concatenated skill bodies relevant to *prompt*."""
        all_skills = self._loader.discover()
        if not all_skills:
            return ""
        selected = self._selector.select(prompt, all_skills) if prompt else all_skills
        if not selected:
            selected = all_skills  # safe fallback
        return "\n\n".join(s.body for s in selected)


class FHIRGuidelinesBuilder:
    """Builds the FHIR code-generation guidelines injected into Stage 2.

    Contains only code-generation rules: sandbox constraints, import paths,
    reference patterns, resource creation order, and the FHIR spec summary.
    Clinical prose is deliberately excluded — it is replaced by the
    structured ClinicalPlan JSON in Stage 2.
    """

    def build(self, fhir_version: str | None = None) -> str:
        if fhir_version is None:
            fhir_version = get_fhir_version()
        system_raw = load_section("system")
        system_text = render(
            system_raw,
            allowed_list=_ALLOWED_LIST,
            allowed_prefixes=_ALLOWED_PREFIXES,
            fhir_version=fhir_version,
        )
        return "\n\n".join([system_text, import_guide(), spec_summary()])


# ── Pipeline ──────────────────────────────────────────────────────────────────


class TwoStagePipeline:
    """Orchestrates the full two-stage generation pipeline.

    Stage 1 — Clinical Planning:
        prompt + skills context → ClinicalPlan (structured, Pydantic-validated)

    Stage 2 — Code Synthesis:
        ClinicalPlan + FHIR guidelines → Python code → FHIR resources

    Post-processing:
        Reference repair → Quality evaluation → PipelineResult

    All collaborators are injected via constructor for full testability and
    adherence to the Dependency Inversion principle.
    """

    def __init__(
        self,
        planner: ClinicalPlanner,
        synthesizer: CodeSynthesizer,
        evaluator: GenerationEvaluator,
        executor: Executor | None = None,
        skill_context_builder: SkillContextBuilder | None = None,
        plan_enricher: ClinicalPlanEnricher | None = None,
    ) -> None:
        self._planner = planner
        self._synthesizer = synthesizer
        self._evaluator = evaluator
        self._executor: Executor = executor or LocalSmolagentsExecutor()
        self._skill_builder = skill_context_builder or SkillContextBuilder()
        self._enricher: ClinicalPlanEnricher = plan_enricher or PlanEnricher()

    def run(self, prompt: str, timeout: int = 30) -> PipelineResult:
        """Execute the full pipeline for *prompt*.

        Args:
            prompt: Natural-language generation request.
            timeout: Execution timeout in seconds.

        Returns:
            PipelineResult with plan, code, resources, and quality report.

        Raises:
            RuntimeError: If code synthesis or execution fails.
        """
        # Stage 1: clinical planning
        logger.info("Stage 1 — Clinical planning for: %r", prompt[:80])
        skills_context = self._skill_builder.build(prompt)
        plan = self._planner.plan(prompt, skills_context)
        logger.info(
            "Stage 1 complete — %d patient(s), setting: %s",
            len(plan.patients),
            plan.care_setting,
        )

        # Stage 1.5: dependency enrichment
        plan = self._enricher.enrich(plan)
        if plan.care_team:
            logger.info(
                "Stage 1.5 — Enriched plan with care team: %s",
                [m.role for m in plan.care_team],
            )

        # Stage 2: code synthesis
        logger.info("Stage 2 — Code synthesis from clinical plan")
        code = self._synthesizer.synthesize(plan)
        code = self._preprocess_code(code)

        # Execution
        logger.info("Executing generated code")
        result = self._executor.execute(code, timeout=timeout)
        resources: list[dict[str, Any]] = result.artifacts

        # Post-processing: reference repair
        resources, repair_report = repair_references(resources)
        if repair_report["repaired"] > 0:
            logger.info("Reference repair: fixed %d reference(s)", repair_report["repaired"])

        # Evaluation
        report = self._evaluator.evaluate(resources)
        logger.info(
            "Quality: %.2f (%s) — FHIR valid: %.0f%%, refs: %.0f%%, US Core: %.0f%%",
            report.overall_score,
            report.grade,
            *[ms.score * 100 for ms in report.metric_scores],
        )

        return PipelineResult(
            plan=plan,
            code=code,
            resources=resources,
            report=report,
            repair_report=repair_report,
        )

    @classmethod
    def default(
        cls,
        llm_provider: Any,
        executor: Executor | None = None,
        user_skill_dirs: list[Path] | None = None,
    ) -> "TwoStagePipeline":
        """Convenience factory using DSPy modules and default collaborators.

        Args:
            llm_provider: An :class:`~fhir_synth.llm.LLMProvider` instance.
                Its ``.model`` string is used to configure DSPy.
            executor: Optional custom executor backend.
            user_skill_dirs: Additional skill directories.

        Returns:
            A fully-configured TwoStagePipeline.
        """
        from fhir_synth.pipeline.dspy_modules import (
            DSPyClinicalPlanner,
            DSPyCodeSynthesizer,
            configure_dspy_lm,
        )

        configure_dspy_lm(model=llm_provider.model)
        guidelines = FHIRGuidelinesBuilder().build()

        return cls(
            planner=DSPyClinicalPlanner(),
            synthesizer=DSPyCodeSynthesizer(fhir_guidelines=guidelines),
            evaluator=GenerationEvaluator(),
            executor=executor,
            skill_context_builder=SkillContextBuilder(user_dirs=user_skill_dirs),
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _preprocess_code(code: str) -> str:
        """Apply import fixes before execution."""
        import_errors = validate_imports(code)
        if import_errors:
            fixed = fix_common_imports(code)
            if not validate_imports(fixed):
                return fixed
        return code
