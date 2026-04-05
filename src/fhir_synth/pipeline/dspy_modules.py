"""DSPy signatures and modules for the two-stage pipeline.

Requires the optional `dspy-ai` dependency:
    pip install 'fhir-synth[dspy]'

Design decisions
----------------
- `PlanFromPromptSignature`: TypedPredictor enforces ClinicalPlan as output,
  giving us Pydantic validation for free.
- `CodeFromPlanSignature`: ChainOfThought lets the model reason step-by-step
  before emitting code — empirically better for structured code generation.
- Both modules implement their corresponding Protocol so they can be used
  interchangeably with non-DSPy stubs in tests.
"""

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


# ── DSPy modules ──────────────────────────────────────────────────────────────


class DSPyClinicalPlanner:
    """Stage 1: converts a natural-language prompt into a ClinicalPlan.

    Implements the ClinicalPlanner protocol.  Uses dspy.Predict with a typed
    Pydantic output field — DSPy 3.x enforces the schema natively.
    """

    def __init__(self) -> None:
        dspy = _require_dspy()
        sig = _make_plan_signature(dspy)
        self._predict = dspy.Predict(sig)

    def plan(self, prompt: str, skills_context: str) -> ClinicalPlan:
        result = self._predict(prompt=prompt, clinical_context=skills_context)
        return result.plan  # type: ignore[no-any-return]

    # DSPy Module interface — forward() mirrors plan() for optimisation
    def forward(self, prompt: str, clinical_context: str) -> Any:
        return self._predict(prompt=prompt, clinical_context=clinical_context)


class DSPyCodeSynthesizer:
    """Stage 2: converts a ClinicalPlan into executable Python code.

    Implements the CodeSynthesizer protocol.  Uses ChainOfThought so the
    model reasons about structure before emitting code.
    """

    def __init__(self, fhir_guidelines: str) -> None:
        dspy = _require_dspy()
        sig = _make_code_signature(dspy)
        self._predict = dspy.ChainOfThought(sig)
        self._fhir_guidelines = fhir_guidelines

    def synthesize(self, plan: ClinicalPlan) -> str:
        result = self._predict(
            plan_json=plan.model_dump_json(indent=2),
            fhir_guidelines=self._fhir_guidelines,
        )
        return _extract_code(result.code)

    def forward(self, plan_json: str, fhir_guidelines: str) -> Any:
        return self._predict(plan_json=plan_json, fhir_guidelines=fhir_guidelines)


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
