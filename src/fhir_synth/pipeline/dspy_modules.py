"""DSPy signatures and modules for the two-stage pipeline.

Requires the optional `dspy-ai` dependency:
    pip install 'fhir-synth[dspy]'

Design decisions
----------------
- `PlanFromPromptSignature`: uses `plan: ClinicalPlan` typed output so DSPy
  provides the JSON schema to the model, enforcing the correct structure.
  `_parse_clinical_plan` is a fallback for models that return malformed JSON.
- `CodeFromPlanSignature`: ChainOfThought lets the model reason step-by-step
  before emitting code — empirically better for structured code generation.
- Both `DSPyClinicalPlanner` and `DSPyCodeSynthesizer` use a ``__new__``
  factory to return genuine ``dspy.Module`` subclass instances.  This keeps
  DSPy as an optional dependency while giving the optimizer full traceability
  and enabling ``dspy.save`` / ``dspy.load`` round-trips.
- `FHIRSynthProgram` is the *composite* module used for optimization.  It
  wraps both stages so ``BootstrapFewShot`` / ``MIPROv2`` can optimize them
  jointly.  After optimization, save with ``dspy.save(program, path)`` and
  reload via ``TwoStagePipeline.from_compiled(path, ...)``.
"""

import ast
import json
import logging
from typing import Any

from fhir_synth.pipeline.models import ClinicalPlan

logger = logging.getLogger(__name__)


def _require_dspy() -> Any:
    try:
        import dspy

        return dspy
    except ImportError as exc:
        raise ImportError(
            "DSPy is required for the two-stage pipeline. "
            "Install it with: pip install 'fhir-synth[dspy]'"
        ) from exc


# ── Signatures ────────────────────────────────────────────────────────────────


def _make_plan_signature(dspy: Any) -> Any:
    class PlanFromPromptSignature(dspy.Signature):  # type: ignore[misc]
        """Generate a structured clinical data plan from a natural language request.

        Focus exclusively on clinical content: realistic disease codes, medication
        names, demographics, and care setting.  Do NOT include FHIR syntax or
        Python code — that happens in the next stage.
        """

        prompt: str = dspy.InputField(
            desc="Natural language description of the healthcare data to generate"
        )
        clinical_context: str = dspy.InputField(
            desc=(
                "Clinical knowledge: coding systems (SNOMED, LOINC, RxNorm), "
                "realistic value ranges, disease co-occurrence patterns"
            )
        )
        plan: ClinicalPlan = dspy.OutputField(
            desc=(
                "Structured clinical plan with one PatientProfile per patient. "
                "Use real codes (SNOMED for conditions, RxNorm for medications). "
                "Include realistic ages, genders, and clinical findings. "
                "For longitudinal prompts (multiple visits, follow-ups, progression over time): "
                "set time_span_months to the total duration and populate each PatientProfile.timeline "
                "with EncounterEvent entries at realistic month_offset intervals. "
                "Each EncounterEvent must include labs with causally consistent values "
                "(e.g. HbA1c trending down after treatment starts), vitals, and medication_changes "
                "that reflect clinical decision-making at that point in the disease course."
            )
        )

    return PlanFromPromptSignature


def _make_code_signature(dspy: Any) -> Any:
    class CodeFromPlanSignature(dspy.Signature):  # type: ignore[misc]
        """Generate Python code that creates FHIR resources from a clinical plan.

        The code must define `generate_resources() -> list[dict]`.
        Use `fhir.resources.{fhir_version}` Pydantic models.
        Call `.model_dump(exclude_none=True)` on every resource.
        Assign consistent UUIDs using `str(uuid4())`.
        """

        plan_json: str = dspy.InputField(
            desc="JSON-encoded ClinicalPlan describing the patients and their clinical data"
        )
        fhir_guidelines: str = dspy.InputField(
            desc=(
                "FHIR import paths, sandbox constraints, reference patterns, "
                "and creation order rules"
            )
        )
        code: str = dspy.OutputField(
            desc=(
                "Complete Python source code.  Must define generate_resources() -> list[dict]. "
                "Return a flat list of resource dicts (no Bundle wrapper)."
            )
        )

    return CodeFromPlanSignature


# ── Internal class factories ───────────────────────────────────────────────────


def _make_clinical_planner_class(dspy_lib: Any) -> type:
    """Return a genuine ``dspy.Module`` subclass for Stage 1 (clinical planning)."""

    class _DSPyClinicalPlanner(dspy_lib.Module):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()
            sig = _make_plan_signature(dspy_lib)
            self._predict = dspy_lib.Predict(sig)

        def plan(self, prompt: str, skills_context: str) -> ClinicalPlan:
            result = self._predict(prompt=prompt, clinical_context=skills_context)
            plan = result.plan
            if isinstance(plan, ClinicalPlan):
                return plan
            return _parse_clinical_plan(str(plan))

        def forward(self, prompt: str, clinical_context: str) -> Any:
            return self._predict(prompt=prompt, clinical_context=clinical_context)

    _DSPyClinicalPlanner.__name__ = "DSPyClinicalPlanner"
    _DSPyClinicalPlanner.__qualname__ = "DSPyClinicalPlanner"
    return _DSPyClinicalPlanner


def _make_code_synthesizer_class(dspy_lib: Any) -> type:
    """Return a genuine ``dspy.Module`` subclass for Stage 2 (code synthesis)."""

    class _DSPyCodeSynthesizer(dspy_lib.Module):  # type: ignore[misc]
        def __init__(self, fhir_guidelines: str) -> None:
            super().__init__()
            sig = _make_code_signature(dspy_lib)
            self._predict = dspy_lib.ChainOfThought(sig)
            self._fhir_guidelines = fhir_guidelines

        def synthesize(self, plan: ClinicalPlan) -> str:
            result = self._predict(
                plan_json=plan.model_dump_json(indent=2),
                fhir_guidelines=self._fhir_guidelines,
            )
            return _extract_code(result.code)

        def forward(self, plan_json: str, fhir_guidelines: str) -> Any:
            return self._predict(plan_json=plan_json, fhir_guidelines=fhir_guidelines)

    _DSPyCodeSynthesizer.__name__ = "DSPyCodeSynthesizer"
    _DSPyCodeSynthesizer.__qualname__ = "DSPyCodeSynthesizer"
    return _DSPyCodeSynthesizer


def _make_fhir_synth_program_class(dspy_lib: Any) -> type:
    """Return a composite ``dspy.Module`` subclass wrapping both stages.

    The optimizer traces through ``forward()`` and can optimize both
    ``_plan_predict`` and ``_code_predict`` jointly.
    """

    class _FHIRSynthProgram(dspy_lib.Module):  # type: ignore[misc]
        def __init__(self, fhir_guidelines: str) -> None:
            super().__init__()
            self._fhir_guidelines = fhir_guidelines
            sig1 = _make_plan_signature(dspy_lib)
            sig2 = _make_code_signature(dspy_lib)
            self._plan_predict = dspy_lib.Predict(sig1)
            self._code_predict = dspy_lib.ChainOfThought(sig2)

        def forward(self, prompt: str, clinical_context: str) -> Any:
            plan_result = self._plan_predict(prompt=prompt, clinical_context=clinical_context)
            plan = plan_result.plan
            if not isinstance(plan, ClinicalPlan):
                plan = _parse_clinical_plan(str(plan))

            code_result = self._code_predict(
                plan_json=plan.model_dump_json(indent=2),
                fhir_guidelines=self._fhir_guidelines,
            )
            return dspy_lib.Prediction(plan=plan, code=_extract_code(code_result.code))

    _FHIRSynthProgram.__name__ = "FHIRSynthProgram"
    _FHIRSynthProgram.__qualname__ = "FHIRSynthProgram"
    return _FHIRSynthProgram


# ── Public DSPy modules ────────────────────────────────────────────────────────


class DSPyClinicalPlanner:
    """Stage 1: converts a natural-language prompt into a `ClinicalPlan`.

    Implements the `ClinicalPlanner` protocol.  Uses `dspy.Predict` with a
    typed Pydantic output field — DSPy 3.x enforces the schema natively.

    Returns a genuine ``dspy.Module`` instance (via ``__new__``) so the
    optimizer can trace through it and ``dspy.save`` / ``dspy.load`` work.
    """

    def __new__(cls) -> Any:
        dspy = _require_dspy()
        klass = _make_clinical_planner_class(dspy)
        return klass()


class DSPyCodeSynthesizer:
    """Stage 2: converts a `ClinicalPlan` into executable Python code.

    Implements the `CodeSynthesizer` protocol.  Uses ``ChainOfThought`` so
    the model reasons about structure before emitting code.

    Returns a genuine ``dspy.Module`` instance (via ``__new__``) so the
    optimizer can trace through it and ``dspy.save`` / ``dspy.load`` work.
    """

    def __new__(cls, fhir_guidelines: str) -> Any:
        dspy = _require_dspy()
        klass = _make_code_synthesizer_class(dspy)
        return klass(fhir_guidelines=fhir_guidelines)


class FHIRSynthProgram:
    """Composite DSPy module wrapping Stage 1 and Stage 2 for optimization.

    Use this as the target for ``dspy.BootstrapFewShot`` or ``MIPROv2``::

        program = FHIRSynthProgram(fhir_guidelines=guidelines)
        optimizer = dspy.BootstrapFewShot(metric=evaluator.dspy_metric)
        compiled = optimizer.compile(program, trainset=examples)
        dspy.save(compiled, "compiled_program.json")

    Then reload via ``TwoStagePipeline.from_compiled("compiled_program.json", ...)``.

    Returns a genuine ``dspy.Module`` instance (via ``__new__``).
    """

    def __new__(cls, fhir_guidelines: str) -> Any:
        dspy = _require_dspy()
        klass = _make_fhir_synth_program_class(dspy)
        return klass(fhir_guidelines=fhir_guidelines)


# ── Compiled program adapters ─────────────────────────────────────────────────


class _CompiledPlannerAdapter:
    """Delegates Stage 1 calls to a loaded ``FHIRSynthProgram``'s planner predictor.

    Used by ``TwoStagePipeline.from_compiled()`` to split the composite program
    back into the separate planner / synthesizer protocol objects.
    """

    def __init__(self, program: Any) -> None:
        self._program = program

    def plan(self, prompt: str, skills_context: str) -> ClinicalPlan:
        result = self._program._plan_predict(prompt=prompt, clinical_context=skills_context)
        plan = result.plan
        if isinstance(plan, ClinicalPlan):
            return plan
        return _parse_clinical_plan(str(plan))


class _CompiledSynthesizerAdapter:
    """Delegates Stage 2 calls to a loaded ``FHIRSynthProgram``'s code predictor.

    Used by ``TwoStagePipeline.from_compiled()`` to split the composite program
    back into the separate planner / synthesizer protocol objects.
    """

    def __init__(self, program: Any, fhir_guidelines: str) -> None:
        self._program = program
        self._fhir_guidelines = fhir_guidelines

    def synthesize(self, plan: ClinicalPlan) -> str:
        result = self._program._code_predict(
            plan_json=plan.model_dump_json(indent=2),
            fhir_guidelines=self._fhir_guidelines,
        )
        return _extract_code(result.code)


# ── LLM configuration helper ──────────────────────────────────────────────────


def configure_dspy_lm(model: str, **kwargs: Any) -> None:
    """Configure DSPy's global language model from a LiteLLM model string.

    This bridges `LLMProvider` model names (which are
    LiteLLM-compatible) directly into DSPy, since DSPy also uses LiteLLM.

    Args:
        model: LiteLLM model string, e.g. `"gpt-4o"`, `"claude-3-5-sonnet"`.
        **kwargs: Extra kwargs forwarded to `dspy.LM` (api_key, api_base, etc.).
    """
    dspy = _require_dspy()
    lm = dspy.LM(model=model, **kwargs)
    dspy.configure(lm=lm)
    logger.debug("DSPy configured with model: %s", model)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _parse_clinical_plan(raw: str) -> ClinicalPlan:
    """Parse a ClinicalPlan from an LM response string.

    Some models return Python dict syntax (single quotes) instead of valid JSON.
    Falls back to ``ast.literal_eval`` so the pipeline doesn't crash on those.
    """
    raw = raw.strip()
    try:
        return ClinicalPlan.model_validate_json(raw)
    except Exception:
        pass
    # Fallback: try ast.literal_eval (handles single-quoted Python dicts)
    try:
        data = ast.literal_eval(raw)
        return ClinicalPlan.model_validate(data)
    except Exception:
        pass
    # Last resort: re-encode via json to normalise any oddities, then parse
    try:
        data = json.loads(raw.replace("'", '"'))
        return ClinicalPlan.model_validate(data)
    except Exception as exc:
        raise ValueError(
            f"Could not parse ClinicalPlan from LM output. First 200 chars: {raw[:200]!r}"
        ) from exc


def _extract_code(raw: str) -> str:
    """Strip Markdown fences from a code string if present."""
    if "```python" in raw:
        start = raw.find("```python") + 9
        end = raw.find("```", start)
        return raw[start:end].strip()
    if "```" in raw:
        start = raw.find("```") + 3
        end = raw.find("```", start)
        return raw[start:end].strip()
    return raw.strip()
