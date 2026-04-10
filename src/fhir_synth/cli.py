"""FHIR Synth CLI - Generate synthetic FHIR data from natural language prompts (supports R4B, STU3)."""

import json
import sys
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = typer.Typer(
    help="Dynamic FHIR synthetic data generator — prompt → code → data (supports R4B, STU3)"
)


def _configure_skills(
    skills_dir: str | None,
    selector: str,
    score_threshold: float | None = None,
) -> dict[str, Any]:
    """Configure the skills system for prompt assembly.

    Args:
        skills_dir: Optional path to a user-provided skills directory.
        selector: Selection strategy name (`"keyword"` or `"faiss"`).
        score_threshold: Minimum similarity score (FAISS only).

    Returns:
        Skill discovery summary dict.
    """
    from fhir_synth.code_generator.prompts import configure_skills, get_skill_discovery_summary

    user_dirs = [Path(skills_dir)] if skills_dir else None
    skill_selector = None
    if selector == "faiss":
        from fhir_synth.skills import FaissSelector

        if score_threshold is not None:
            skill_selector = FaissSelector(score_threshold=score_threshold)
        else:
            skill_selector = FaissSelector()
    configure_skills(user_dirs=user_dirs, selector=skill_selector)
    return get_skill_discovery_summary()


@app.command()
def generate(
    prompt: str = typer.Argument(..., help="Natural language description of data to generate"),
    provider: str = typer.Option("gpt-4", "--provider", "-p", help="LLM model/provider"),
    fhir_version: str = typer.Option(
        "R4B", "--fhir-version", help="FHIR version: R4B, STU3 (case-insensitive)"
    ),
    empi: bool = typer.Option(False, "--empi", help="Include EMPI Person/Patient linkage"),
    persons: int = typer.Option(1, "--persons", help="Number of Persons for EMPI"),
    systems: str = typer.Option("emr1,emr2", "--systems", help="Comma-separated EMR system ids"),
    no_orgs: bool = typer.Option(False, "--no-orgs", help="Do not create Organization resources"),
    meta_config: str | None = typer.Option(
        None, "--meta-config", help="YAML file with metadata configuration"
    ),
    split: bool = typer.Option(
        False,
        "--split",
        help="Also split output into one JSON file per patient in a subdirectory",
    ),
    aws_profile: str | None = typer.Option(
        None, "--aws-profile", help="AWS profile for Bedrock (reads ~/.aws/credentials)"
    ),
    aws_region: str | None = typer.Option(
        None, "--aws-region", help="AWS region for Bedrock (e.g. us-east-1)"
    ),
    executor_backend: str = typer.Option(
        "local",
        "--executor",
        "-e",
        help="Execution backend: local, docker, e2b, or blaxel (all powered by smolagents)",
    ),
    skills_dir: str | None = typer.Option(
        None, "--skills-dir", help="Directory with user-provided SKILL.md skills"
    ),
    selector: str = typer.Option(
        "keyword",
        "--selector",
        help="Skill selection strategy: keyword (fuzzy matching with typo tolerance) or faiss (semantic similarity)",
    ),
    score_threshold: float | None = typer.Option(
        None,
        "--score-threshold",
        help="Minimum similarity score 0.0-1.0 (FAISS only, default: 0.3)",
    ),
    context: str | None = typer.Option(
        None,
        "--context",
        help="Path to NDJSON or JSON file with existing FHIR resources for stateful generation",
    ),
    pipeline: str = typer.Option(
        "default",
        "--pipeline",
        help="Generation pipeline: 'default' (single-stage) or 'dspy' (two-stage clinical planning, requires fhir-synth[dspy])",
    ),
    compiled_program: str | None = typer.Option(
        None,
        "--compiled-program",
        help="Path to a compiled DSPy program JSON (from dspy.save). Only used with --pipeline dspy.",
    ),
) -> None:
    """Generate synthetic FHIR data end-to-end: prompt → LLM → code → execute → NDJSON.

    All outputs are saved to a `runs/<name>/` directory with an auto-generated
    Docker-style name (e.g. `brave_phoenix`).  Each run produces:

    - `runs/<name>/prompt.txt`     — the user's prompt
    - `runs/<name>/<name>.py`      — the generated Python code
    - `runs/<name>/<name>.ndjson`  — NDJSON data (one patient bundle per line)
    - `runs/<name>/patient_*.json` — (with --split) per-patient JSON files

    Example prompts:

      # Diabetes cohort with labs
      fhir-synth generate "10 diabetic patients with HbA1c observations"

      # Cardiology patients with encounters and meds
      fhir-synth generate "5 patients with hypertension, office encounters, and antihypertensive medications"

      # Emergency department visits
      fhir-synth generate "8 patients with ER encounters for chest pain, troponin labs, and ECG procedures"

      # Oncology cohort
      fhir-synth generate "6 lung cancer patients with staging observations, chemotherapy medication requests, and CT scan diagnostic reports"

      # Pediatric immunizations
      fhir-synth generate "10 pediatric patients aged 0-5 with immunization records for DTaP, MMR, and IPV"

      # Mental health
      fhir-synth generate "5 patients with major depressive disorder, PHQ-9 observations, and SSRI prescriptions"

      # Prenatal care
      fhir-synth generate "4 pregnant patients with prenatal encounters, ultrasound procedures, and pregnancy-related observations"

      # Multi-condition elderly
      fhir-synth generate "10 elderly patients aged 65-90 with diabetes, hypertension, CKD, encounters, labs, and medications"

      # Surgical patients
      fhir-synth generate "5 patients with appendectomy procedures, pre-op encounters, and post-op follow-up encounters"

      # Allergy and immunology
      fhir-synth generate "8 patients with allergy intolerances to penicillin and peanuts, plus related encounters"

      # EMPI cross-system linkage
      fhir-synth generate "3 patients" --empi --persons 3 --systems emr1,emr2,lab_system

      # With metadata (security labels, tags, profiles)
      fhir-synth generate "10 patients" --meta-config examples/meta-normal.yaml

      # Split into per-patient files (also creates the NDJSON)
      fhir-synth generate "20 patients with conditions" --split

      # AWS Bedrock provider
      fhir-synth generate "5 patients" --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 --aws-profile my-profile --aws-region us-east-1

      # Use Docker sandbox executor for sandboxed execution (requires Docker)
      fhir-synth generate "5 patients" --executor docker

      # E2B cloud sandbox (requires E2B_API_KEY env var)
      fhir-synth generate "5 patients" --executor e2b

      # Blaxel cloud sandbox
      fhir-synth generate "5 patients" --executor blaxel

      # Generate STU3 resources instead of R4B
      fhir-synth generate "10 patients with diabetes" --fhir-version STU3

      # Use custom skills directory
      fhir-synth generate "5 patients" --skills-dir ~/.fhir-synth/skills

      # Use FAISS semantic skill selection (requires: pip install fhir-synth[semantic])
      fhir-synth generate "5 patients" --selector faiss

      # FAISS with a custom similarity threshold
      fhir-synth generate "5 patients" --selector faiss --score-threshold 0.5
    """
    try:
        from fhir_synth.code_generator import CodeGenerator, get_executor
        from fhir_synth.llm import get_provider
        from fhir_synth.naming import create_run_dir

        # ── Create run directory & output paths ─────────────────────
        run_dir = create_run_dir()
        run_name = run_dir.name
        code_path = run_dir / f"{run_name}.py"
        ndjson_path = run_dir / f"{run_name}.ndjson"
        prompt_path = run_dir / "prompt.txt"
        prompt_path.write_text(prompt)
        typer.echo(f"📂 Run: {run_dir}")

        # ── Configure skills system ────────────────────────────────
        discovery = _configure_skills(skills_dir, selector, score_threshold)
        builtin_n = discovery["builtin"]
        user_n = discovery["user"]
        total_n = discovery["total"]
        typer.echo(f"📚 Skills: discovered {total_n} ({builtin_n} built-in, {user_n} user)")
        if user_n:
            user_names = [s["name"] for s in discovery["skills"] if s["source"] == "user"]
            typer.echo(f"   User skills: {', '.join(user_names)}")

        # ── Load context resources ──────────────────────────────────
        context_resources: list[dict[str, Any]] = []
        if context:
            context_path = Path(context)
            if context_path.exists():
                if context_path.suffix == ".ndjson":
                    with context_path.open() as f:
                        for line in f:
                            if line.strip():
                                try:
                                    res = json.loads(line)
                                    # If it's a bundle, extract entries
                                    if res.get("resourceType") == "Bundle":
                                        for entry in res.get("entry", []):
                                            if "resource" in entry:
                                                context_resources.append(entry["resource"])
                                    else:
                                        context_resources.append(res)
                                except json.JSONDecodeError:
                                    continue
                else:
                    res = json.loads(context_path.read_text())
                    if isinstance(res, list):
                        context_resources.extend(res)
                    elif res.get("resourceType") == "Bundle":
                        for entry in res.get("entry", []):
                            if "resource" in entry:
                                context_resources.append(entry["resource"])
                    else:
                        context_resources.append(res)
                typer.echo(f"   Loaded {len(context_resources)} resources from context")

        typer.echo(f"🤖 LLM: {provider}")
        typer.echo(f"   Executor: {executor_backend}")

        llm = get_provider(provider, aws_profile=aws_profile, aws_region=aws_region)
        executor = get_executor(executor_backend)
        code_gen = CodeGenerator(
            llm,
            executor=executor,
            fhir_version=fhir_version,
            context_resources=context_resources,
        )

        # Load metadata configuration from YAML if provided
        prompt_text = prompt
        # dspy_prompt stays free of metadata instructions — Stage 1 is clinical
        # planning only; metadata (security labels, profiles, tags) is applied
        # as post-processing on the generated resources (step 2.5).
        dspy_prompt = prompt
        metadata_config = None

        if meta_config:
            import yaml

            with open(meta_config) as f:
                metadata_config = yaml.safe_load(f)

            # Build prompt hints from YAML config
            metadata_hints: list[str] = []
            meta = metadata_config.get("meta", {})

            if meta.get("security"):
                for sec in meta["security"]:
                    metadata_hints.append(
                        f"Add security label: system={sec.get('system')}, "
                        f"code={sec.get('code')}, display={sec.get('display', sec.get('code'))}"
                    )

            if meta.get("tag"):
                for tag in meta["tag"]:
                    metadata_hints.append(
                        f"Add tag: system={tag.get('system')}, "
                        f"code={tag.get('code')}, display={tag.get('display', tag.get('code'))}"
                    )

            if meta.get("profile"):
                for prof in meta["profile"]:
                    metadata_hints.append(f"Add profile: {prof}")

            if meta.get("source"):
                metadata_hints.append(f"Set meta.source to: {meta['source']}")

            if metadata_hints:
                metadata_instructions = "METADATA REQUIREMENTS:\n" + "\n".join(
                    f"- {hint}" for hint in metadata_hints
                )
                prompt_text = f"{metadata_instructions}\n\n{prompt_text}"
                # dspy_prompt deliberately not updated here

        # Augment prompt with EMPI hints if requested
        if empi:
            from fhir_synth.code_generator.prompts import build_empi_prompt

            system_list = [s.strip() for s in systems.split(",") if s.strip()]
            prompt_text = build_empi_prompt(
                user_prompt=prompt_text,
                persons=persons,
                systems=system_list or None,
                include_organizations=not no_orgs,
            )
            # EMPI is clinical context — include it for DSPy too
            dspy_prompt = build_empi_prompt(
                user_prompt=dspy_prompt,
                persons=persons,
                systems=system_list or None,
                include_organizations=not no_orgs,
            )

        if pipeline == "dspy":
            # ── Two-stage DSPy pipeline ──────────────────────────────────
            from fhir_synth.pipeline.pipeline import TwoStagePipeline

            if compiled_program:
                typer.echo(f"⚙  Two-stage pipeline (compiled): loading {compiled_program} …")
                two_stage = TwoStagePipeline.from_compiled(
                    compiled_path=Path(compiled_program),
                    llm_provider=llm,
                    executor=executor,
                    user_skill_dirs=[Path(skills_dir)] if skills_dir else None,
                )
            else:
                typer.echo("⚙  Two-stage pipeline: clinical planning → code synthesis …")
                two_stage = TwoStagePipeline.default(
                    llm_provider=llm,
                    executor=executor,
                    user_skill_dirs=[Path(skills_dir)] if skills_dir else None,
                )
            pipeline_result = two_stage.run(dspy_prompt)
            resources = pipeline_result.resources
            code = pipeline_result.code
            code_path.write_text(code)
            if pipeline_result.selected_skills:
                typer.echo(
                    f"   🎯 Selected {len(pipeline_result.selected_skills)}/{pipeline_result.total_skills} skills: "
                    f"{', '.join(pipeline_result.selected_skills)}"
                )
            typer.echo(f"   Stage 1 plan: {len(pipeline_result.plan.patients)} patient(s)")
            typer.echo(f"   Saved code → {code_path}")
            typer.echo(
                f"   Quality: {pipeline_result.report.overall_score:.2f} "
                f"({pipeline_result.report.grade})"
            )
        else:
            # ── Default single-stage pipeline ────────────────────────────
            # Step 1 — generate code
            typer.echo("⚙  Generating code from prompt …")

            from fhir_synth.code_generator.prompts import get_selected_skill_names

            selected_names = get_selected_skill_names(prompt_text)
            if selected_names:
                typer.echo(
                    f"   🎯 Selected {len(selected_names)}/{total_n} skills: "
                    f"{', '.join(selected_names)}"
                )
            else:
                typer.echo("   ⚠️  No skills matched — using all available skills")

            code = code_gen.generate_code_from_prompt(prompt_text)
            code_path.write_text(code)
            typer.echo(f"   Saved code → {code_path}")

            # Step 2 — execute code (self-healing retries built-in)
            typer.echo("▶  Executing generated code …")
            resources = code_gen.execute_generated_code(code)

        # Step 2.1 — report FHIR validation
        from fhir_synth.code_generator.fhir_validation import validate_resources

        vr = validate_resources(resources)
        if vr.is_valid:
            typer.echo(f"   ✅ {vr.total} resources — all valid FHIR {fhir_version}")
        else:
            typer.echo(
                f"   ⚠️  {vr.total} resources — {vr.valid} valid, "
                f"{vr.invalid} invalid ({vr.pass_rate:.0%} pass rate)"
            )
            for err in vr.errors[:5]:
                typer.echo(
                    f"      ❌ {err['resourceType']}/{err['id']}: {'; '.join(err['errors'][:2])}",
                    err=True,
                )

        # Step 2.2 — report reference integrity
        from fhir_synth.code_generator.fhir_validation import validate_references

        ref_errors = validate_references(resources)
        broken_refs = sum(len(e.get("errors", [])) for e in ref_errors)
        if broken_refs == 0:
            typer.echo("   ✅ Reference integrity — all references valid")
        else:
            typer.echo(f"   ⚠️  Reference integrity — {broken_refs} broken reference(s)")
            for entry in ref_errors[:3]:
                for err in entry.get("errors", [])[:2]:
                    typer.echo(f"      ↳ {entry['resourceType']}/{entry['id']}: {err}", err=True)

        # Step 2.3 — report US Core compliance
        from fhir_synth.code_generator.us_core_validation import validate_us_core

        ucr = validate_us_core(resources)
        if ucr.total_checked > 0:
            if not ucr.has_warnings:
                typer.echo(f"   ✅ US Core — {ucr.total_checked} resources fully compliant")
            else:
                non_compliant = ucr.total_checked - ucr.fully_compliant
                typer.echo(
                    f"   ⚠️  US Core — {non_compliant}/{ucr.total_checked} resources "
                    f"missing must-support fields ({ucr.compliance_rate:.0%} compliant)"
                )
                for w in ucr.warnings[:3]:
                    missing = ", ".join(w["missing_must_support"][:3])
                    typer.echo(
                        f"      ↳ {w['resourceType']}/{w['id']}: missing {missing}",
                        err=True,
                    )

        # Step 2.5 — apply metadata from YAML config if specified
        if metadata_config and "meta" in metadata_config:
            from fhir_synth.code_generator import CodeGenerator

            meta = metadata_config["meta"]
            CodeGenerator.apply_metadata_to_resources(
                resources,
                security=meta.get("security"),
                tag=meta.get("tag"),
                profile=meta.get("profile"),
                source=meta.get("source"),
            )
            typer.echo("   Applied metadata from config")

        # Step 3 — output results
        from fhir_synth.bundle import split_resources_by_patient, write_ndjson, write_split_bundles

        per_patient_bundles = split_resources_by_patient(resources)

        # Always write NDJSON
        write_ndjson(per_patient_bundles, ndjson_path)
        typer.echo(f"✓  {len(per_patient_bundles)} patient bundles → {ndjson_path}")

        # --split: also write per-patient JSON files into run directory
        if split:
            paths = write_split_bundles(per_patient_bundles, run_dir)
            typer.echo(f"✓  {len(paths)} patient files → {run_dir}/")

    except Exception as exc:
        error_msg = str(exc)

        # Provide helpful error messages based on error type
        if "No module named" in error_msg or "ImportError" in error_msg or "Import" in error_msg:
            typer.echo("❌ Import error detected", err=True)
            typer.echo(f"   {exc}", err=True)
            typer.echo("\n💡 Suggestions:", err=True)
            typer.echo("   1. Try a more reliable provider: --provider gpt-4", err=True)
            typer.echo("   2. Check the saved code in runs/", err=True)
            typer.echo("   3. The LLM may have used incorrect import paths", err=True)
        elif "Code execution failed" in error_msg:
            typer.echo("❌ Code execution failed after retries", err=True)
            typer.echo(f"   {exc}", err=True)
            typer.echo("\n💡 Check the saved code in runs/", err=True)
        else:
            typer.echo(f"❌ Error: {exc}", err=True)

        sys.exit(1)


@app.command()
def codegen(
    prompt: str = typer.Argument(..., help="Natural language description of data"),
    out: str = typer.Option(..., "--out", "-o", help="Output file for code"),
    provider: str = typer.Option("mock", "--provider", help="LLM provider"),
    fhir_version: str = typer.Option(
        "R4B", "--fhir-version", help="FHIR version: R4B, STU3 (case-insensitive)"
    ),
    execute: bool = typer.Option(False, "--execute", "-x", help="Execute the code"),
    empi: bool = typer.Option(False, "--empi", help="Include EMPI Person/Patient linkage"),
    persons: int = typer.Option(1, "--persons", help="Number of Persons for EMPI"),
    systems: str = typer.Option("emr1,emr2", "--systems", help="Comma-separated EMR system ids"),
    no_orgs: bool = typer.Option(False, "--no-orgs", help="Do not create Organization resources"),
    aws_profile: str | None = typer.Option(
        None, "--aws-profile", help="AWS profile for Bedrock (reads ~/.aws/credentials)"
    ),
    aws_region: str | None = typer.Option(
        None, "--aws-region", help="AWS region for Bedrock (e.g. us-east-1)"
    ),
    executor_backend: str = typer.Option(
        "local",
        "--executor",
        "-e",
        help="Execution backend: local, docker, e2b, or blaxel (all powered by smolagents)",
    ),
    skills_dir: str | None = typer.Option(
        None, "--skills-dir", help="Directory with user-provided SKILL.md skills"
    ),
    selector: str = typer.Option(
        "keyword",
        "--selector",
        help="Skill selection strategy: keyword (fuzzy matching with typo tolerance) or faiss (semantic similarity)",
    ),
    score_threshold: float | None = typer.Option(
        None,
        "--score-threshold",
        help="Minimum similarity score 0.0-1.0 (FAISS only, default: 0.3)",
    ),
) -> None:
    """Generate Python code for resource creation from a prompt."""
    try:
        from fhir_synth.code_generator import CodeGenerator, get_executor
        from fhir_synth.llm import get_provider

        # ── Configure skills system ────────────────────────────────
        discovery = _configure_skills(skills_dir, selector, score_threshold)
        builtin_n = discovery["builtin"]
        user_n = discovery["user"]
        total_n = discovery["total"]
        typer.echo(f"📚 Skills: discovered {total_n} ({builtin_n} built-in, {user_n} user)")
        if user_n:
            user_names = [s["name"] for s in discovery["skills"] if s["source"] == "user"]
            typer.echo(f"   User skills: {', '.join(user_names)}")

        typer.echo(f"🤖 LLM: {provider}")

        llm = get_provider(provider, aws_profile=aws_profile, aws_region=aws_region)
        executor = get_executor(executor_backend)
        code_gen = CodeGenerator(llm, max_retries=2, executor=executor, fhir_version=fhir_version)
        prompt_text = prompt
        if empi:
            from fhir_synth.code_generator.prompts import build_empi_prompt

            system_list = [s.strip() for s in systems.split(",") if s.strip()]
            prompt_text = build_empi_prompt(
                user_prompt=prompt,
                persons=persons,
                systems=system_list or None,
                include_organizations=not no_orgs,
            )

        # Show which skills were selected for this prompt
        from fhir_synth.code_generator.prompts import get_selected_skill_names

        selected_names = get_selected_skill_names(prompt_text)
        if selected_names:
            typer.echo(
                f"   🎯 Selected {len(selected_names)}/{total_n} skills: "
                f"{', '.join(selected_names)}"
            )

        code = code_gen.generate_code_from_prompt(prompt_text)

        Path(out).write_text(code)
        typer.echo(f"✓ Generated code: {out}")

        if execute:
            typer.echo("Executing generated code...")
            resources = code_gen.execute_generated_code(code)
            typer.echo(f"✓ Generated {len(resources)} resources")

            results_file = Path(out).stem + "_results.json"
            Path(results_file).write_text(json.dumps(resources, indent=2, default=str))
            typer.echo(f"✓ Results: {results_file}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@app.command()
def optimize(
    training_dir: str = typer.Option(
        "",
        "--training-dir",
        "-t",
        help="Directory with *_prompt.txt training pairs (default: runs/training_examples_diverse if exists, else runs/training_examples)",
    ),
    output: str = typer.Option(
        "runs/optimized_pipeline.json",
        "--output",
        "-o",
        help="Path to save the compiled DSPy program",
    ),
    provider: str = typer.Option(
        "gpt-4o-mini", "--provider", "-p", help="LLM model for optimization"
    ),
    max_demos: int = typer.Option(
        3,
        "--max-demos",
        help="Max bootstrapped demos per predictor (bootstrap only — MIPROv2 uses --auto preset)",
    ),
    optimizer: str = typer.Option(
        "bootstrap",
        "--optimizer",
        help="Optimizer: 'bootstrap' (BootstrapFewShot) or 'miprov2' (MIPROv2 — optimizes instructions)",
    ),
    auto: str = typer.Option(
        "light", "--auto", help="MIPROv2 intensity: 'light', 'medium', or 'heavy' (MIPROv2 only)"
    ),
) -> None:
    """Optimize the two-stage DSPy pipeline using BootstrapFewShot or MIPROv2.

    Loads training prompts, runs the selected optimizer, and saves the compiled
    program for use with:

        fhir-synth generate "..." --pipeline dspy --compiled-program runs/optimized_pipeline.json

    Requires: pip install 'fhir-synth[dspy]'

    Examples:

        fhir-synth optimize --provider gpt-4o-mini --max-demos 3
        fhir-synth optimize --optimizer miprov2 --provider deepseek/deepseek-chat --auto light
    """
    try:
        import dspy
    except ImportError:
        typer.echo("❌ DSPy not installed: pip install 'fhir-synth[dspy]'", err=True)
        raise typer.Exit(1)

    from fhir_synth.pipeline.evaluator import GenerationEvaluator
    from fhir_synth.pipeline.pipeline import TwoStagePipeline

    # Resolve training dir
    t_dir = Path(training_dir) if training_dir else None
    if t_dir is None:
        diverse = Path("runs/training_examples_diverse")
        t_dir = diverse if diverse.exists() else Path("runs/training_examples")
    typer.echo(f"📂 Training dir: {t_dir}")

    prompt_files = sorted(t_dir.glob("*_prompt.txt"))
    if not prompt_files:
        typer.echo(f"❌ No *_prompt.txt files found in {t_dir}", err=True)
        raise typer.Exit(1)

    prompts = [f.read_text().strip() for f in prompt_files]
    typer.echo(f"📚 Loaded {len(prompts)} training prompts")

    from fhir_synth.code_generator.executor import LocalSmolagentsExecutor
    from fhir_synth.code_generator.fhir_validation import repair_references
    from fhir_synth.pipeline.dspy_modules import FHIRSynthProgram as _FHIRSynthProgram
    from fhir_synth.pipeline.dspy_modules import configure_dspy_lm
    from fhir_synth.pipeline.pipeline import FHIRGuidelinesBuilder, SkillContextBuilder

    configure_dspy_lm(model=provider)
    guidelines = FHIRGuidelinesBuilder().build()
    skill_builder = SkillContextBuilder()
    evaluator = GenerationEvaluator()

    # FHIRSynthProgram is the composite module with _plan_predict + _code_predict —
    # exactly the structure from_compiled expects.
    fhir_program: Any = _FHIRSynthProgram(fhir_guidelines=guidelines)

    # Wrapper adds skill context, executes code, and returns resources for the metric.
    class _OptModule(dspy.Module):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()
            self.fhir_program = fhir_program

        def forward(self, prompt: str) -> dspy.Prediction:
            clinical_context = skill_builder.build(prompt)
            result = self.fhir_program(prompt=prompt, clinical_context=clinical_context)
            code = TwoStagePipeline.preprocess_code(result.code)
            ex = LocalSmolagentsExecutor().execute(code, timeout=30)
            resources, _ = repair_references(ex.artifacts)
            return dspy.Prediction(resources=resources, plan=result.plan, code=code)

    module = _OptModule()
    trainset = [dspy.Example(prompt=p).with_inputs("prompt") for p in prompts]

    if optimizer == "miprov2":
        typer.echo(f"⚙  Running MIPROv2 (auto={auto}, max_demos={max_demos})…")
        dspy_optimizer = dspy.MIPROv2(
            metric=evaluator.dspy_metric,
            auto=auto,
            max_errors=100,
        )
        optimized = dspy_optimizer.compile(module, trainset=trainset)
    else:
        typer.echo(f"⚙  Running BootstrapFewShot (max_demos={max_demos})…")
        dspy_optimizer = dspy.BootstrapFewShot(
            metric=evaluator.dspy_metric,
            max_bootstrapped_demos=max_demos,
            max_labeled_demos=0,
        )
        optimized = dspy_optimizer.compile(module, trainset=trainset)

    from fhir_synth.naming import create_run_dir

    if output and output != "runs/optimized_pipeline.json":
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = create_run_dir()
        out_path = run_dir / "optimized_pipeline.json"
    # Save the inner FHIRSynthProgram — from_compiled loads this structure directly.
    optimized.fhir_program.save(str(out_path))
    typer.echo(f"✓ Compiled program saved → {out_path}")
    typer.echo("\nTo use it:")
    typer.echo(f'  fhir-synth generate "your prompt" --pipeline dspy --compiled-program {out_path}')


@app.command()
def bundle(
    resources: str | None = typer.Option(None, "--resources", "-r", help="Input NDJSON file"),
    out: str = typer.Option(..., "--out", "-o", help="Output Bundle JSON file"),
    bundle_type: str = typer.Option("transaction", "--type", help="Bundle type"),
) -> None:
    """Create a FHIR Bundle from NDJSON resources."""
    from fhir_synth.bundle import BundleBuilder

    try:
        if not resources:
            raise ValueError("--resources is required")

        builder = BundleBuilder(bundle_type=bundle_type)
        with open(resources) as handle:
            for line in handle:
                if line.strip():
                    builder.add_resource(json.loads(line))

        _bundle = builder.build()
        Path(out).write_text(json.dumps(_bundle, indent=2, default=str))
        typer.echo(f"✓ Created bundle with {_bundle['total']} entries: {out}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
