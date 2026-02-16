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
) -> None:
    """Generate declarative rules from a natural language prompt."""
    try:
        from fhir_synth.code_generator import PromptToRulesConverter
        from fhir_synth.llm import get_provider

        llm = get_provider(provider)
        converter = PromptToRulesConverter(llm)
        rules_result = converter.convert_prompt_to_rules(prompt)

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
) -> None:
    """Generate Python code for resource creation from a prompt."""
    try:
        from fhir_synth.code_generator import CodeGenerator
        from fhir_synth.llm import get_provider

        llm = get_provider(provider)
        code_gen = CodeGenerator(llm)
        code = code_gen.generate_code_from_prompt(prompt)

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
    resources: str = typer.Option(..., "--resources", "-r", help="Input NDJSON file"),
    out: str = typer.Option(..., "--out", "-o", help="Output Bundle JSON file"),
    bundle_type: str = typer.Option("transaction", "--type", help="Bundle type"),
) -> None:
    """Create a FHIR Bundle from NDJSON resources."""
    from fhir_synth.bundle_builder import BundleBuilder

    try:
        builder = BundleBuilder(bundle_type=bundle_type)

        with open(resources) as handle:
            for line in handle:
                if line.strip():
                    builder.add_resource(json.loads(line))

        bundle = builder.build()
        Path(out).write_text(json.dumps(bundle, indent=2, default=str))
        typer.echo(f"✓ Created bundle with {bundle['total']} entries: {out}")
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
