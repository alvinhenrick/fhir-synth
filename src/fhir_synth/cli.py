"""FHIR Synth CLI - Generate synthetic FHIR R4B data from natural language prompts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = typer.Typer(help="Dynamic FHIR R4B synthetic data generator")


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
        code_gen = CodeGenerator(llm)
        prompt_text = prompt
        if empi:
            system_list = [s.strip() for s in systems.split(",") if s.strip()]
            orgs_hint = "Do not create Organization resources." if no_orgs else "Create Organization resources for each system and link Patients via managingOrganization."
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
    resources: str | None = typer.Option(
        None, "--resources", "-r", help="Input NDJSON file"
    ),
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
