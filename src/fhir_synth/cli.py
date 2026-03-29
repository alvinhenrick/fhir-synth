"""FHIR Synth CLI - Generate synthetic FHIR data from natural language prompts (supports R4B, STU3)."""

import json
import sys
from pathlib import Path

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
) -> None:
    """Configure the skills system for prompt assembly.

    Args:
        skills_dir: Optional path to a user-provided skills directory.
        selector: Selection strategy name (``"keyword"`` or ``"faiss"``).
        score_threshold: Minimum similarity score (FAISS only).
    """
    from fhir_synth.code_generator.prompts import configure_skills

    user_dirs = [Path(skills_dir)] if skills_dir else None
    skill_selector = None
    if selector == "faiss":
        from fhir_synth.skills import FaissSelector

        if score_threshold is not None:
            skill_selector = FaissSelector(score_threshold=score_threshold)
        else:
            skill_selector = FaissSelector()
    configure_skills(user_dirs=user_dirs, selector=skill_selector)


@app.command()
def generate(
    prompt: str = typer.Argument(..., help="Natural language description of data to generate"),
    out: str = typer.Option("output.ndjson", "--out", "-o", help="Output file path"),
    provider: str = typer.Option("gpt-4", "--provider", "-p", help="LLM model/provider"),
    fhir_version: str = typer.Option(
        "R4B", "--fhir-version", help="FHIR version: R4B, STU3 (case-insensitive)"
    ),
    save_code: str | None = typer.Option(
        None, "--save-code", help="Also save generated code to this file"
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
        help="Split output into one JSON file per patient in a directory",
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
    docker_host: str | None = typer.Option(
        None, "--docker-host", help="Docker host for docker executor (default: 127.0.0.1)"
    ),
    docker_port: int | None = typer.Option(
        None, "--docker-port", help="Docker port for docker executor (default: 8888)"
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
) -> None:
    """Generate synthetic FHIR data end-to-end: prompt → LLM → code → execute → NDJSON.

    The default output is a single NDJSON file (one patient bundle per line).
    Use --split to write one JSON file per patient into a directory instead.

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

      # Split into per-patient files
      fhir-synth generate "20 patients with conditions" --split -o patients/

      # AWS Bedrock provider
      fhir-synth generate "5 patients" --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 --aws-profile my-profile --aws-region us-east-1

      # Save generated code for debugging
      fhir-synth generate "10 patients with labs" --save-code generated.py

      # Use Docker sandbox executor for sandboxed execution (requires Docker)
      fhir-synth generate "5 patients" --executor docker

      # Docker sandbox with explicit host/port
      fhir-synth generate "5 patients" --executor docker --docker-host 127.0.0.1 --docker-port 8888

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

        # ── Configure skills system ────────────────────────────────
        _configure_skills(skills_dir, selector, score_threshold)

        # ── Load context resources ──────────────────────────────────
        context_resources = []
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

        llm = get_provider(provider, aws_profile=aws_profile, aws_region=aws_region)
        executor = get_executor(
            executor_backend,
            docker_host=docker_host,
            docker_port=docker_port,
        )
        code_gen = CodeGenerator(
            llm,
            executor=executor,
            fhir_version=fhir_version,
            context_resources=context_resources,
        )

        # Load metadata configuration from YAML if provided
        prompt_text = prompt
        metadata_config = None

        if meta_config:
            import yaml

            with open(meta_config) as f:
                metadata_config = yaml.safe_load(f)

            # Build prompt hints from YAML config
            metadata_hints = []
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

        # Step 1 — generate code
        typer.echo("⚙  Generating code from prompt …")
        code = code_gen.generate_code_from_prompt(prompt_text)

        if save_code:
            Path(save_code).write_text(code)
            typer.echo(f"   Saved code → {save_code}")

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

        # Step 2.5 — apply metadata from YAML config if specified
        if metadata_config and "meta" in metadata_config:
            meta = metadata_config["meta"]
            code_gen.apply_metadata_to_resources(
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

        if split:
            # --split: one JSON file per patient in a directory
            out_dir = Path(out)
            paths = write_split_bundles(per_patient_bundles, out_dir)
            typer.echo(f"✓  {len(paths)} patient bundles → {out_dir}/")
        else:
            # Default: single NDJSON file (one bundle per patient per line)
            out_path = Path(out)
            if out_path.suffix != ".ndjson":
                out_path = out_path.with_suffix(".ndjson")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            ndjson_path = write_ndjson(per_patient_bundles, out_path)
            typer.echo(f"✓  {len(per_patient_bundles)} patient bundles → {ndjson_path}")
    except Exception as exc:
        error_msg = str(exc)

        # Provide helpful error messages based on error type
        if "No module named" in error_msg or "ImportError" in error_msg or "Import" in error_msg:
            typer.echo("❌ Import error detected", err=True)
            typer.echo(f"   {exc}", err=True)
            typer.echo("\n💡 Suggestions:", err=True)
            typer.echo("   1. Try a more reliable provider: --provider gpt-4", err=True)
            if save_code:
                typer.echo(f"   2. Check the saved code: {save_code}", err=True)
            else:
                typer.echo("   2. Save and inspect the code: --save-code output.py", err=True)
            typer.echo("   3. The LLM may have used incorrect import paths", err=True)
        elif "Code execution failed" in error_msg:
            typer.echo("❌ Code execution failed after retries", err=True)
            typer.echo(f"   {exc}", err=True)
            if save_code:
                typer.echo(f"\n💡 Check the saved code: {save_code}", err=True)
            else:
                typer.echo(
                    "\n💡 Try: --save-code output.py to inspect the generated code", err=True
                )
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
    docker_host: str | None = typer.Option(
        None, "--docker-host", help="Docker host for docker executor (default: 127.0.0.1)"
    ),
    docker_port: int | None = typer.Option(
        None, "--docker-port", help="Docker port for docker executor (default: 8888)"
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
        _configure_skills(skills_dir, selector, score_threshold)

        llm = get_provider(provider, aws_profile=aws_profile, aws_region=aws_region)
        executor = get_executor(
            executor_backend,
            docker_host=docker_host,
            docker_port=docker_port,
        )
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
