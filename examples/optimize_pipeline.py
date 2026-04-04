"""DSPy optimization example for the two-stage FHIR generation pipeline.

This script shows how to use DSPy's BootstrapFewShot optimizer to automatically
improve the clinical planning and code synthesis prompts based on your quality metrics.

Prerequisites
-------------
    pip install 'fhir-synth[dspy]'
    export OPENAI_API_KEY=sk-...   # or ANTHROPIC_API_KEY, etc.

Usage
-----
    python examples/optimize_pipeline.py

What it does
------------
1.  Defines a small trainset of (prompt → expected resource types) examples.
2.  Runs BootstrapFewShot to find few-shot examples that maximize the
    GenerationEvaluator score (FHIR validity + reference integrity + US Core).
3.  Saves the optimized DSPy module state to ``optimized_pipeline.json``.
4.  Demonstrates how to load and reuse the optimized module.

Notes
-----
- The quality metric is ``GenerationEvaluator.dspy_metric`` — the same scorer
  used in the pipeline.  No separate labelling step is needed.
- BootstrapFewShot is the right first optimizer: zero labelled data required,
  works well with 3-10 training examples, fast to run.
- For production, consider MIPROv2 once you have 20+ examples.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Training examples ─────────────────────────────────────────────────────────
# Each example is just a prompt string.  The metric evaluates the generated
# resources — no ground-truth labels needed.

TRAIN_PROMPTS = [
    "3 patients with Type 2 diabetes, each on Metformin, with HbA1c observations",
    "2 patients with hypertension on Lisinopril, with blood pressure readings",
    "1 elderly patient with COPD, albuterol inhaler, and spirometry result",
    "2 patients with heart failure, BNP lab results, and furosemide prescriptions",
    "1 pregnant patient at 28 weeks with prenatal visits and glucose tolerance test",
]


def build_trainset() -> list[dict[str, str]]:
    """Build DSPy-compatible training examples from plain prompts."""
    import dspy  # type: ignore[import-untyped]

    return [dspy.Example(prompt=p).with_inputs("prompt") for p in TRAIN_PROMPTS]


# ── DSPy wrapper module ───────────────────────────────────────────────────────


def make_optimizable_module(pipeline: "TwoStagePipeline") -> "dspy.Module":  # type: ignore[name-defined]
    """Wrap TwoStagePipeline.run() as a DSPy Module for optimization.

    DSPy's optimizers work on Modules with a forward() method.
    We wrap the pipeline so the optimizer can tune the planner's prompts.
    """
    import dspy  # type: ignore[import-untyped]

    class PipelineModule(dspy.Module):  # type: ignore[misc]
        def __init__(self, inner: "TwoStagePipeline") -> None:  # type: ignore[name-defined]
            super().__init__()
            self._pipeline = inner
            # Expose the DSPy planner's internal predictor for optimization
            if hasattr(inner._planner, "_predict"):
                self.planner_predict = inner._planner._predict

        def forward(self, prompt: str) -> "dspy.Prediction":  # type: ignore[name-defined]
            result = self._pipeline.run(prompt)
            return dspy.Prediction(
                resources=result.resources,
                plan=result.plan,
                code=result.code,
                quality_score=result.report.overall_score,
            )

    return PipelineModule(pipeline)


# ── Main optimization flow ────────────────────────────────────────────────────


def main() -> None:
    try:
        import dspy  # type: ignore[import-untyped]
    except ImportError:
        logger.error("dspy-ai is not installed. Run: pip install 'fhir-synth[dspy]'")
        return

    from fhir_synth.llm import get_provider
    from fhir_synth.pipeline.evaluator import GenerationEvaluator
    from fhir_synth.pipeline.pipeline import TwoStagePipeline

    # ── 1. Configure LLM ──────────────────────────────────────────────────────
    model = os.getenv("FHIR_SYNTH_MODEL", "gpt-4o-mini")
    logger.info("Configuring DSPy with model: %s", model)
    dspy.configure(lm=dspy.LM(model=model))

    # ── 2. Build pipeline ─────────────────────────────────────────────────────
    llm = get_provider(model)
    pipeline = TwoStagePipeline.default(llm_provider=llm)
    evaluator = GenerationEvaluator()

    # ── 3. Wrap for DSPy optimization ─────────────────────────────────────────
    module = make_optimizable_module(pipeline)
    trainset = build_trainset()
    logger.info("Training set: %d examples", len(trainset))

    # ── 4. Run BootstrapFewShot ───────────────────────────────────────────────
    # metric: higher overall_score = better
    optimizer = dspy.BootstrapFewShot(
        metric=evaluator.dspy_metric,
        max_bootstrapped_demos=3,
        max_labeled_demos=0,  # zero labelled data needed
    )

    logger.info("Starting optimization (this will make LLM calls)…")
    optimized = optimizer.compile(module, trainset=trainset)
    logger.info("Optimization complete.")

    # ── 5. Save optimized module ──────────────────────────────────────────────
    out_path = Path("optimized_pipeline.json")
    optimized.save(str(out_path))
    logger.info("Saved optimized module → %s", out_path)

    # ── 6. Verify on a held-out prompt ───────────────────────────────────────
    test_prompt = "5 patients with chronic kidney disease, creatinine labs, and ACE inhibitors"
    logger.info("Running optimized pipeline on: %r", test_prompt)
    pred = optimized(prompt=test_prompt)
    score = evaluator.evaluate(pred.resources).overall_score
    logger.info("Quality score: %.2f (%s)", score, evaluator.evaluate(pred.resources).grade)

    # ── 7. Show how to reload ─────────────────────────────────────────────────
    logger.info("\nTo reuse the optimized module:")
    logger.info("  module = make_optimizable_module(pipeline)")
    logger.info("  module.load('%s')", out_path)
    logger.info("  result = module(prompt='...')")

    return score


if __name__ == "__main__":
    score = main()
    if score is not None:
        print(f"\nFinal quality score: {score:.2f}")
