"""FHIR Synth MCP server — expose fhir-synth as Claude tools.

After ``pip install "fhir-synth[mcp]"`` the ``fhir-synth-mcp`` console script
is available. Wire it into Claude Desktop / Claude Code via ``mcpServers``:

    {
      "mcpServers": {
        "fhir-synth": {
          "command": "fhir-synth-mcp",
          "env": {
            "FHIR_SYNTH_PROVIDER": "claude-sonnet-4-5",
            "ANTHROPIC_API_KEY": "sk-ant-..."
          }
        }
      }
    }

Configuration via environment variables:
    FHIR_SYNTH_PROVIDER       LiteLLM model string. Default: "claude-sonnet-4-5".
    ANTHROPIC_API_KEY         For Anthropic direct
    OPENAI_API_KEY            For OpenAI
    AWS_PROFILE / AWS_REGION  For Bedrock
    FHIR_SYNTH_PIPELINE       "default" or "dspy". Default: "default".
    FHIR_SYNTH_COMPILED       Which compiled DSPy program to load (when
                              FHIR_SYNTH_PIPELINE=dspy). Accepts:
                                "miprov2"    — bundled MIPROv2-optimized program (default)
                                "bootstrap"  — bundled BootstrapFewShot program
                                "/abs/path/file.json" — your own compiled program
                                "none"       — use the unoptimized DSPy default
    FHIR_SYNTH_EXECUTOR       "local" (default), "docker", "e2b", "blaxel".
    FHIR_SYNTH_RUNS_DIR       Where run artefacts are written. Default: "runs".
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from fhir_synth.compiled_programs import resolve_compiled_program
from fhir_synth.reporter import MCPReporter

load_dotenv()

# ── Configuration (read once at startup) ──────────────────────────────────────

_PROVIDER = os.environ.get("FHIR_SYNTH_PROVIDER", "claude-sonnet-4-5")
_AWS_PROFILE = os.environ.get("AWS_PROFILE")
_AWS_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
_PIPELINE = os.environ.get("FHIR_SYNTH_PIPELINE", "default").lower()
_COMPILED_DEFAULT = os.environ.get("FHIR_SYNTH_COMPILED", "miprov2")
_EXECUTOR = os.environ.get("FHIR_SYNTH_EXECUTOR", "local")
_RUNS_DIR = Path(os.environ.get("FHIR_SYNTH_RUNS_DIR", "runs"))


# ── MCP server ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "fhir-synth",
    instructions=(
        "Generate synthetic FHIR healthcare data from natural language prompts. "
        "Use generate_fhir_data to produce both FHIR resources AND a reusable Python "
        "script. The script can be committed and called from test fixtures — no LLM "
        "needed after the initial generation. Use validate_fhir_bundle to check "
        "existing FHIR data, list_skills to discover supported clinical domains, and "
        "list_runs / get_run to retrieve previously generated artefacts."
    ),
)


def _get_llm() -> Any:
    from fhir_synth.llm import get_provider

    return get_provider(_PROVIDER, aws_profile=_AWS_PROFILE, aws_region=_AWS_REGION)


def _quality_summary(resources: list[dict[str, Any]]) -> dict[str, Any]:
    from fhir_synth.code_generator.fhir_validation import validate_references, validate_resources
    from fhir_synth.code_generator.us_core_validation import validate_us_core

    vr = validate_resources(resources)
    ref_errors = validate_references(resources)
    broken_refs = sum(len(e.get("errors", [])) for e in ref_errors)
    ucr = validate_us_core(resources)

    return {
        "fhir_total": vr.total,
        "fhir_valid": vr.valid,
        "fhir_invalid": vr.invalid,
        "fhir_pass_rate": round(vr.pass_rate, 3),
        "broken_references": broken_refs,
        "us_core_total_checked": ucr.total_checked,
        "us_core_fully_compliant": ucr.fully_compliant,
        "us_core_compliance_rate": (
            round(ucr.compliance_rate, 3) if ucr.total_checked > 0 else None
        ),
        "fhir_errors_sample": vr.errors[:5],
        "reference_errors_sample": ref_errors[:3],
    }


# ── Tool 1: generate_fhir_data ───────────────────────────────────────────────


@mcp.tool()
async def generate_fhir_data(
    prompt: str,
    fhir_version: str = "R4B",
    split: bool = False,
    pipeline: str | None = None,
    compiled_program: str | None = None,
    meta_config: dict[str, Any] | None = None,
    max_resources_returned: int = 200,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Generate synthetic FHIR data from a natural language prompt.

    Returns the generated Python code AND the executed FHIR resources. The code is
    self-contained — commit it to your repo and call ``generate_resources()`` from
    pytest fixtures or any other consumer. No LLM needed for replay.

    Args:
        prompt: Natural language request, e.g. "10 diabetic patients with HbA1c labs".
        fhir_version: "R4B" (default) or "STU3".
        split: Also write per-patient JSON files in the run directory.
        pipeline: Override the default pipeline. Accepts:
            "default" — single-stage code generation (no DSPy required, fastest)
            "dspy"    — two-stage clinical planning → code synthesis (higher
                        quality, requires `pip install fhir-synth[dspy]`)
            Leave None to use the FHIR_SYNTH_PIPELINE env var (default: "default").
            Override only when the user explicitly asks for higher quality, the
            two-stage / clinical planning pipeline, or names a compiled program.
        compiled_program: Which compiled DSPy program to load (only honored when
            pipeline resolves to "dspy"). Accepts:
            "miprov2"     — bundled MIPROv2-optimized program (best quality)
            "bootstrap"   — bundled BootstrapFewShot program (faster)
            "/abs/path"   — user's own compiled JSON
            "none"        — unoptimized DSPy default
            Leave None to use the FHIR_SYNTH_COMPILED env var (default: "miprov2").
        meta_config: Optional FHIR Meta to stamp on every generated resource —
            security labels, tags, profiles, source. Only pass when the user
            explicitly asks for metadata (most generations skip this).

            Schema (mirrors the ``--meta-config`` YAML used by the CLI)::

                {
                  "meta": {
                    "security": [
                      {"system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                       "code": "R", "display": "Restricted"}
                    ],
                    "tag": [
                      {"system": "http://example.org/tags",
                       "code": "synthetic-data", "display": "Synthetic Test Data"}
                    ],
                    "profile": [
                      "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
                    ],
                    "source": "http://example.org/fhir-synth"
                  }
                }

            All four sub-fields are individually optional. Inline what the user
            asks for; omit the rest. Examples in ``examples/meta-normal.yaml``
            and ``examples/meta-restricted.yaml`` show real-world shapes.
        max_resources_returned: Cap on resources inlined in the response (full set
            is always written to NDJSON). Use ``get_run`` to fetch the rest.
    """
    from fhir_synth.bundle import (
        split_resources_by_patient,
        write_ndjson,
        write_split_bundles,
    )
    from fhir_synth.code_generator import CodeGenerator, get_executor
    from fhir_synth.code_generator.prompts import (
        configure_skills,
        get_selected_skill_names,
        get_skill_discovery_summary,
        reset_skills,
    )
    from fhir_synth.naming import create_run_dir

    reporter = MCPReporter(ctx)
    total_steps = 6

    reset_skills()
    configure_skills()

    run_dir = create_run_dir(_RUNS_DIR)
    run_name = run_dir.name
    code_path = run_dir / f"{run_name}.py"
    ndjson_path = run_dir / f"{run_name}.ndjson"
    (run_dir / "prompt.txt").write_text(prompt)
    await reporter.info(f"📂 Run: {run_dir}")
    await reporter.progress(1, total_steps, "run directory created")

    discovery = get_skill_discovery_summary()
    await reporter.info(
        f"📚 Skills: discovered {discovery['total']} "
        f"({discovery['builtin']} built-in, {discovery['user']} user)"
    )

    llm = _get_llm()
    executor = get_executor(_EXECUTOR)
    await reporter.info(f"🤖 LLM: {_PROVIDER}")
    await reporter.info(f"   Executor: {_EXECUTOR}")

    selected_skills = get_selected_skill_names(prompt)
    if selected_skills:
        await reporter.info(
            f"🎯 Selected {len(selected_skills)}/{discovery['total']} skills: "
            f"{', '.join(selected_skills)}"
        )
    else:
        await reporter.warning("No skills matched — using all available skills")

    effective_pipeline = (pipeline or _PIPELINE).lower()
    effective_compiled_spec = (
        compiled_program if compiled_program is not None else _COMPILED_DEFAULT
    )

    # Build the prompt the LLM actually sees — augment with metadata hints when
    # the caller passed meta_config. The clinical-planning stage of the DSPy
    # pipeline should stay metadata-free (metadata is post-processing), so we
    # only augment the prompt used by the single-stage pipeline.
    metadata_prompt = prompt
    meta_dict = meta_config.get("meta") if isinstance(meta_config, dict) else None
    if isinstance(meta_dict, dict):
        hints: list[str] = []
        for sec in meta_dict.get("security") or []:
            hints.append(
                f"Add security label: system={sec.get('system')}, "
                f"code={sec.get('code')}, display={sec.get('display', sec.get('code'))}"
            )
        for tag in meta_dict.get("tag") or []:
            hints.append(
                f"Add tag: system={tag.get('system')}, "
                f"code={tag.get('code')}, display={tag.get('display', tag.get('code'))}"
            )
        for prof in meta_dict.get("profile") or []:
            hints.append(f"Add profile: {prof}")
        if meta_dict.get("source"):
            hints.append(f"Set meta.source to: {meta_dict['source']}")
        if hints:
            metadata_prompt = (
                "METADATA REQUIREMENTS:\n" + "\n".join(f"- {h}" for h in hints) + f"\n\n{prompt}"
            )

    if effective_pipeline == "dspy":
        try:
            from fhir_synth.pipeline.pipeline import TwoStagePipeline
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "The DSPy pipeline requires the optional dspy extra. "
                "Install with:  pip install 'fhir-synth[dspy]'"
            ) from exc

        compiled = resolve_compiled_program(effective_compiled_spec)
        if compiled is not None:
            await reporter.info(f"⚙  Two-stage pipeline (compiled): loading {compiled} …")
            two_stage = TwoStagePipeline.from_compiled(
                compiled_path=compiled,
                llm_provider=llm,
                executor=executor,
            )
            pipeline_mode = f"dspy (compiled: {compiled.name})"
        else:
            await reporter.info("⚙  Two-stage pipeline: clinical planning → code synthesis …")
            two_stage = TwoStagePipeline.default(llm_provider=llm, executor=executor)
            pipeline_mode = "dspy (unoptimized)"

        await reporter.progress(2, total_steps, "generating code (DSPy two-stage)")
        # DSPy clinical-planning stage skips metadata hints; metadata is applied
        # as post-processing below for both pipelines.
        result = two_stage.run(prompt)
        code = result.code
        resources = result.resources
        selected_skills = result.selected_skills or selected_skills
        await reporter.info(f"   Stage 1 plan: {len(result.plan.patients)} patient(s)")
        await reporter.info(
            f"   Quality: {result.report.overall_score:.2f} ({result.report.grade})"
        )
        await reporter.progress(3, total_steps, "code executed")
    else:
        pipeline_mode = "default"
        await reporter.info("⚙  Generating code from prompt …")
        await reporter.progress(2, total_steps, "generating code")
        code_gen = CodeGenerator(llm, executor=executor, fhir_version=fhir_version)
        code = code_gen.generate_code_from_prompt(metadata_prompt)
        await reporter.info("▶  Executing generated code …")
        resources = code_gen.execute_generated_code(code)
        await reporter.progress(3, total_steps, "code executed")

    code_path.write_text(code)
    await reporter.info(f"   Saved code → {code_path}")

    # ── Validation reports (mirrors CLI step 2.1–2.3) ──────────────────────
    from fhir_synth.code_generator.fhir_validation import (
        validate_references,
        validate_resources,
    )
    from fhir_synth.code_generator.us_core_validation import validate_us_core

    vr = validate_resources(resources)
    if vr.is_valid:
        await reporter.info(f"   ✅ {vr.total} resources — all valid FHIR {fhir_version}")
    else:
        await reporter.warning(
            f"{vr.total} resources — {vr.valid} valid, "
            f"{vr.invalid} invalid ({vr.pass_rate:.0%} pass rate)"
        )

    ref_errors = validate_references(resources)
    broken_refs = sum(len(e.get("errors", [])) for e in ref_errors)
    if broken_refs == 0:
        await reporter.info("   ✅ Reference integrity — all references valid")
    else:
        await reporter.warning(f"Reference integrity — {broken_refs} broken reference(s)")

    ucr = validate_us_core(resources)
    if ucr.total_checked > 0:
        if not ucr.has_warnings:
            await reporter.info(f"   ✅ US Core — {ucr.total_checked} resources fully compliant")
        else:
            non_compliant = ucr.total_checked - ucr.fully_compliant
            await reporter.warning(
                f"US Core — {non_compliant}/{ucr.total_checked} resources "
                f"missing must-support fields ({ucr.compliance_rate:.0%} compliant)"
            )
    await reporter.progress(4, total_steps, "validation complete")

    # Stamp the FHIR Meta on each resource (post-processing, both pipelines).
    if isinstance(meta_dict, dict):
        CodeGenerator.apply_metadata_to_resources(
            resources,
            security=meta_dict.get("security"),
            tag=meta_dict.get("tag"),
            profile=meta_dict.get("profile"),
            source=meta_dict.get("source"),
        )
        await reporter.info("   Applied metadata from config")

    per_patient = split_resources_by_patient(resources)
    write_ndjson(per_patient, ndjson_path)
    await reporter.info(f"✓  {len(per_patient)} patient bundles → {ndjson_path}")
    if split:
        paths = write_split_bundles(per_patient, run_dir)
        await reporter.info(f"✓  {len(paths)} patient files → {run_dir}/")
    await reporter.progress(5, total_steps, "output written")

    quality = {
        "fhir_total": vr.total,
        "fhir_valid": vr.valid,
        "fhir_invalid": vr.invalid,
        "fhir_pass_rate": round(vr.pass_rate, 3),
        "broken_references": broken_refs,
        "us_core_total_checked": ucr.total_checked,
        "us_core_fully_compliant": ucr.fully_compliant,
        "us_core_compliance_rate": (
            round(ucr.compliance_rate, 3) if ucr.total_checked > 0 else None
        ),
        "fhir_errors_sample": vr.errors[:5],
        "reference_errors_sample": ref_errors[:3],
    }
    await reporter.progress(6, total_steps, "done")

    return {
        "run_name": run_name,
        "run_dir": str(run_dir),
        "pipeline": pipeline_mode,
        "provider": _PROVIDER,
        "executor": _EXECUTOR,
        "code": code,
        "code_path": str(code_path),
        "ndjson_path": str(ndjson_path),
        "resource_count": len(resources),
        "patient_count": len(per_patient),
        "selected_skills": selected_skills,
        "quality": quality,
        "resources": resources[:max_resources_returned],
        "resources_truncated": len(resources) > max_resources_returned,
    }


# ── Tool 2: validate_fhir_bundle ─────────────────────────────────────────────


@mcp.tool()
async def validate_fhir_bundle(bundle: str, ctx: Context | None = None) -> dict[str, Any]:
    """Validate an existing FHIR payload (Bundle, list of resources, or NDJSON).

    Runs Pydantic validation, cross-resource reference integrity, and US Core
    must-support compliance. Useful for sanity-checking data you didn't generate
    here.

    Args:
        bundle: A JSON string. Accepted shapes:
                  - a FHIR Bundle (``{"resourceType": "Bundle", "entry": [...]}``)
                  - a list of resources (``[{...}, {...}]``)
                  - NDJSON (one JSON object per line)
    """
    from fhir_synth.code_generator.fhir_validation import (
        validate_references,
        validate_resources,
    )
    from fhir_synth.code_generator.us_core_validation import validate_us_core

    reporter = MCPReporter(ctx)
    total = 4

    bundle = bundle.strip()
    resources: list[dict[str, Any]] = []

    if "\n" in bundle and not bundle.startswith("["):
        for line in bundle.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("resourceType") == "Bundle":
                for entry in obj.get("entry", []):
                    if "resource" in entry:
                        resources.append(entry["resource"])
            else:
                resources.append(obj)
    else:
        obj = json.loads(bundle)
        if isinstance(obj, list):
            resources = obj
        elif obj.get("resourceType") == "Bundle":
            resources = [e["resource"] for e in obj.get("entry", []) if "resource" in e]
        else:
            resources = [obj]

    await reporter.info(f"📥 Parsed {len(resources)} resource(s) from input")
    await reporter.progress(1, total, "input parsed")

    vr = validate_resources(resources)
    if vr.is_valid:
        await reporter.info(f"   ✅ FHIR validation — {vr.total} resources valid")
    else:
        await reporter.warning(
            f"FHIR validation — {vr.valid}/{vr.total} valid ({vr.pass_rate:.0%})"
        )
    await reporter.progress(2, total, "FHIR validation complete")

    ref_errors = validate_references(resources)
    broken_refs = sum(len(e.get("errors", [])) for e in ref_errors)
    if broken_refs == 0:
        await reporter.info("   ✅ Reference integrity — all references valid")
    else:
        await reporter.warning(f"Reference integrity — {broken_refs} broken reference(s)")
    await reporter.progress(3, total, "reference check complete")

    ucr = validate_us_core(resources)
    if ucr.total_checked > 0:
        if not ucr.has_warnings:
            await reporter.info(f"   ✅ US Core — {ucr.total_checked} resources fully compliant")
        else:
            non_compliant = ucr.total_checked - ucr.fully_compliant
            await reporter.warning(
                f"US Core — {non_compliant}/{ucr.total_checked} resources "
                f"missing must-support fields ({ucr.compliance_rate:.0%} compliant)"
            )
    await reporter.progress(4, total, "validation done")

    return {
        "input_resource_count": len(resources),
        "fhir_total": vr.total,
        "fhir_valid": vr.valid,
        "fhir_invalid": vr.invalid,
        "fhir_pass_rate": round(vr.pass_rate, 3),
        "broken_references": broken_refs,
        "us_core_total_checked": ucr.total_checked,
        "us_core_fully_compliant": ucr.fully_compliant,
        "us_core_compliance_rate": (
            round(ucr.compliance_rate, 3) if ucr.total_checked > 0 else None
        ),
        "fhir_errors_sample": vr.errors[:5],
        "reference_errors_sample": ref_errors[:3],
    }


# ── Tool 3: list_skills ──────────────────────────────────────────────────────


@mcp.tool()
async def list_skills(ctx: Context | None = None) -> dict[str, Any]:
    """List all clinical-domain skills fhir-synth knows about.

    Useful before writing a prompt — tells you which conditions, resource types,
    and trigger words are covered out of the box (medications, vitals, SDOH, etc.).
    """
    from fhir_synth.skills import SkillLoader

    reporter = MCPReporter(ctx)
    loader = SkillLoader()
    skills = loader.discover()
    builtin_n = sum(1 for s in skills if s.source == "builtin")
    user_n = sum(1 for s in skills if s.source == "user")
    await reporter.info(f"📚 Skills: {len(skills)} total ({builtin_n} built-in, {user_n} user)")
    return {
        "total": len(skills),
        "builtin": builtin_n,
        "user": user_n,
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "source": s.source,
                "resource_types": list(s.resource_types),
                "always": s.always,
            }
            for s in skills
        ],
    }


# ── Tool 4: list_runs ────────────────────────────────────────────────────────


@mcp.tool()
async def list_runs(limit: int = 20, ctx: Context | None = None) -> dict[str, Any]:
    """List recent generation runs in the runs/ directory.

    Args:
        limit: Maximum number of runs to return (newest first).
    """
    reporter = MCPReporter(ctx)
    if not _RUNS_DIR.exists():
        await reporter.warning(f"Runs directory does not exist: {_RUNS_DIR}")
        return {"runs_dir": str(_RUNS_DIR), "runs": []}

    entries = []
    for d in sorted(_RUNS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        prompt_file = d / "prompt.txt"
        ndjson = next(d.glob("*.ndjson"), None)
        code = next(d.glob("*.py"), None)
        entries.append(
            {
                "name": d.name,
                "modified": d.stat().st_mtime,
                "prompt": prompt_file.read_text().strip() if prompt_file.exists() else None,
                "has_code": code is not None,
                "has_ndjson": ndjson is not None,
            }
        )
        if len(entries) >= limit:
            break

    await reporter.info(f"📂 Found {len(entries)} run(s) in {_RUNS_DIR}")
    return {"runs_dir": str(_RUNS_DIR), "runs": entries}


# ── Tool 5: get_run ──────────────────────────────────────────────────────────


@mcp.tool()
async def get_run(
    run_name: str,
    include_resources: bool = True,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Fetch a previously generated run: prompt, code, and resources.

    Args:
        run_name: The directory name (e.g. "brave_phoenix").
        include_resources: When False, omit the resources array (returns only
            prompt + code + counts). Useful for large runs.
    """
    reporter = MCPReporter(ctx)
    run_dir = _RUNS_DIR / run_name
    if not run_dir.is_dir():
        await reporter.warning(f"Run not found: {run_dir}")
        raise ValueError(f"Run not found: {run_dir}")

    prompt_file = run_dir / "prompt.txt"
    code_file = next(run_dir.glob("*.py"), None)
    ndjson_file = next(run_dir.glob("*.ndjson"), None)

    resources: list[dict[str, Any]] = []
    if ndjson_file:
        with ndjson_file.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("resourceType") == "Bundle":
                    for entry in obj.get("entry", []):
                        if "resource" in entry:
                            resources.append(entry["resource"])
                else:
                    resources.append(obj)

    payload: dict[str, Any] = {
        "run_name": run_name,
        "run_dir": str(run_dir),
        "prompt": prompt_file.read_text().strip() if prompt_file.exists() else None,
        "code": code_file.read_text() if code_file else None,
        "code_path": str(code_file) if code_file else None,
        "ndjson_path": str(ndjson_file) if ndjson_file else None,
        "resource_count": len(resources),
    }
    if include_resources:
        payload["resources"] = resources
    await reporter.info(f"📦 Loaded run '{run_name}' — {len(resources)} resource(s)")
    return payload


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (for Claude Desktop / Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
