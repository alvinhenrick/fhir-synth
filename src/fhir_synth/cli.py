"""FHIR Synth CLI - Generate synthetic FHIR R4B data from natural language prompts."""

import json
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = typer.Typer(help="Dynamic FHIR R4B synthetic data generator — prompt → code → data")


@app.command()
def generate(
    prompt: str = typer.Argument(..., help="Natural language description of data to generate"),
    out: str = typer.Option("output.json", "--out", "-o", help="Output file (JSON bundle)"),
    provider: str = typer.Option("gpt-4", "--provider", "-p", help="LLM model/provider"),
    bundle_type: str = typer.Option("transaction", "--type", "-t", help="Bundle type"),
    save_code: str | None = typer.Option(
        None, "--save-code", help="Also save generated code to this file"
    ),
    empi: bool = typer.Option(False, "--empi", help="Include EMPI Person/Patient linkage"),
    persons: int = typer.Option(1, "--persons", help="Number of Persons for EMPI"),
    systems: str = typer.Option("emr1,emr2", "--systems", help="Comma-separated EMR system ids"),
    no_orgs: bool = typer.Option(False, "--no-orgs", help="Do not create Organization resources"),
) -> None:
    """Generate synthetic FHIR data end-to-end: prompt → LLM → code → execute → bundle.

    This is the main command. Describe what data you need in plain English
    and get a valid FHIR R4B Bundle back.

    Examples:

      fhir-synth generate "10 diabetic patients with HbA1c labs" -o diabetes.json

      fhir-synth generate "5 patients with hypertension and encounters" --provider gpt-4 -o hypertension.json

      fhir-synth generate "EMPI dataset" --empi --persons 3 -o empi.json
    """
    try:
        from fhir_synth.bundle_builder import BundleBuilder
        from fhir_synth.code_generator import CodeGenerator
        from fhir_synth.llm import get_provider

        llm = get_provider(provider)
        code_gen = CodeGenerator(llm)

        # Augment prompt with EMPI hints if requested
        prompt_text = prompt
        if empi:
            system_list = [s.strip() for s in systems.split(",") if s.strip()]
            orgs_hint = (
                "Do not create Organization resources."
                if no_orgs
                else "Create Organization resources for each system and link Patients via managingOrganization."
            )
            empi_hint = (
                "Include EMPI linkage: generate Person resources, each linked to "
                "one Patient per system via Person.link.target. "
                f"Systems: {', '.join(system_list or ['emr1', 'emr2'])}. "
                f"Persons: {persons}. {orgs_hint}"
            )
            prompt_text = f"{empi_hint}\n\n{prompt}"

        # Step 1 — generate code
        typer.echo("⚙  Generating code from prompt …")
        code = code_gen.generate_code_from_prompt(prompt_text)

        if save_code:
            Path(save_code).write_text(code)
            typer.echo(f"   Saved code → {save_code}")

        # Step 2 — execute code (self-healing retries built-in)
        typer.echo("▶  Executing generated code …")
        resources = code_gen.execute_generated_code(code)
        typer.echo(f"   Got {len(resources)} resources")

        # Step 3 — wrap in a bundle
        builder = BundleBuilder(bundle_type=bundle_type)
        builder.add_resources(resources)
        bundle_dict = builder.build()

        Path(out).write_text(json.dumps(bundle_dict, indent=2, default=str))
        typer.echo(f"✓  Bundle with {bundle_dict['total']} entries → {out}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@app.command()
def rules(
    prompt: str = typer.Argument(..., help="Natural language description of data"),
    out: str = typer.Option(..., "--out", "-o", help="Output file for rules (JSON)"),
    provider: str = typer.Option("mock", "--provider", help="LLM provider"),
    empi: bool = typer.Option(False, "--empi", help="Include EMPI Person/Patient linkage"),
    persons: int = typer.Option(1, "--persons", help="Number of Persons for EMPI"),
    systems: str = typer.Option("emr1,emr2", "--systems", help="Comma-separated EMR system ids"),
    no_orgs: bool = typer.Option(False, "--no-orgs", help="Do not create Organization resources"),
) -> None:
    """Generate declarative rules from a natural language prompt."""
    try:
        from fhir_synth.code_generator import PromptToRulesConverter
        from fhir_synth.llm import get_provider

        llm = get_provider(provider)
        converter = PromptToRulesConverter(llm)
        rules_result = converter.convert_prompt_to_rules(prompt)

        if empi:
            system_list = [s.strip() for s in systems.split(",") if s.strip()]
            empi_config = {
                "persons": persons,
                "systems": system_list or ["emr1", "emr2"],
                "include_organizations": not no_orgs,
            }
            if isinstance(rules_result, dict):
                rules_result = {**rules_result, "empi": empi_config}
            else:
                rules_result = {"rules": rules_result, "empi": empi_config}

        Path(out).write_text(json.dumps(rules_result, indent=2))
        typer.echo(f"✓ Generated rules: {out}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@app.command()
def codegen(
    prompt: str = typer.Argument(..., help="Natural language description of data"),
    out: str = typer.Option(..., "--out", "-o", help="Output file for code"),
    provider: str = typer.Option("mock", "--provider", help="LLM provider"),
    execute: bool = typer.Option(False, "--execute", "-x", help="Execute the code"),
    empi: bool = typer.Option(False, "--empi", help="Include EMPI Person/Patient linkage"),
    persons: int = typer.Option(1, "--persons", help="Number of Persons for EMPI"),
    systems: str = typer.Option("emr1,emr2", "--systems", help="Comma-separated EMR system ids"),
    no_orgs: bool = typer.Option(False, "--no-orgs", help="Do not create Organization resources"),
) -> None:
    """Generate Python code for resource creation from a prompt."""
    try:
        from fhir_synth.code_generator import CodeGenerator
        from fhir_synth.llm import get_provider

        llm = get_provider(provider)
        code_gen = CodeGenerator(llm, max_retries=2)
        prompt_text = prompt
        if empi:
            system_list = [s.strip() for s in systems.split(",") if s.strip()]
            orgs_hint = (
                "Do not create Organization resources."
                if no_orgs
                else "Create Organization resources for each system and link Patients via managingOrganization."
            )
            empi_hint = (
                "Include EMPI linkage: generate Person resources, each linked to one Patient per system via Person.link.target. "
                f"Systems: {', '.join(system_list or ['emr1', 'emr2'])}. "
                f"Persons: {persons}. {orgs_hint}"
            )
            prompt_text = f"{empi_hint}\n\n{prompt}"

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
    empi: bool = typer.Option(False, "--empi", help="Generate EMPI Person/Patient bundle"),
    persons: int = typer.Option(1, "--persons", help="Number of Persons for EMPI"),
    systems: str = typer.Option("emr1,emr2", "--systems", help="Comma-separated EMR system ids"),
    no_orgs: bool = typer.Option(False, "--no-orgs", help="Do not create Organization resources"),
) -> None:
    """Create a FHIR Bundle from NDJSON resources or EMPI defaults."""
    from fhir_synth.bundle_builder import BundleBuilder
    from fhir_synth.rule_engine import RuleEngine

    try:
        builder = BundleBuilder(bundle_type=bundle_type)

        if empi:
            system_list = [s.strip() for s in systems.split(",") if s.strip()]
            resources_list = RuleEngine.generate_empi_resources(
                persons=persons,
                systems=system_list or None,
                include_organizations=not no_orgs,
            )
            builder.add_resources(resources_list)
        else:
            if not resources:
                raise ValueError("--resources is required unless --empi is set")
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
