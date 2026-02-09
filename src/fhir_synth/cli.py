"""Command-line interface for fhir-synth."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from dotenv import load_dotenv

from fhir_synth.generator import DatasetGenerator
from fhir_synth.plan import DatasetPlan
from fhir_synth.validation import validate_dataset
from fhir_synth.writers import write_output

# Load environment variables from .env file at CLI entry point
# This ensures all env vars are available throughout the application
load_dotenv()

app = typer.Typer()


@app.command()
def init(
    minimal: bool = typer.Option(False, help="Create minimal example config"),
    full: bool = typer.Option(False, help="Create full example config with all options"),
    multi_org: bool = typer.Option(False, help="Create multi-org example config"),
    output: str = typer.Option("examples", help="Output directory for example configs"),
) -> None:
    """Initialize sample configuration files."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    if not any([minimal, full, multi_org]):
        # Default: create all
        minimal = full = multi_org = True

    if minimal:
        _create_minimal_config(output_path)
        typer.echo(f"Created minimal config: {output_path / 'minimal.yml'}")

    if full:
        _create_full_config(output_path)
        typer.echo(f"Created full config: {output_path / 'full.yml'}")

    if multi_org:
        _create_multi_org_config(output_path)
        typer.echo(f"Created multi-org config: {output_path / 'multi-org.yml'}")


@app.command()
def prompt(
    prompt_text: str = typer.Argument(..., help="Prompt for config generation"),
    out: str = typer.Option(..., "--out", "-o", help="Output config file path"),
    provider: str = typer.Option(
        "mock",
        "--provider",
        help="LLM provider to use (e.g., gpt-4, claude-3-opus, mock). API keys loaded from .env file or environment variables.",
    ),
) -> None:
    """Convert prompt to validated config YAML.

    This command uses an LLM to convert natural language descriptions into structured
    configuration files. API keys are automatically loaded from:
    1. .env file in the project root (recommended)
    2. Environment variables (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY)

    Example:
        # Create .env file with your API key
        echo "OPENAI_API_KEY=sk-..." > .env

        # Then use the prompt command
        fhir-synth prompt "50 patients with diabetes" --out config.yml --provider gpt-4

        # Or use the default mock provider (no API key needed)
        fhir-synth prompt "50 patients with diabetes" --out config.yml
    """
    try:
        from fhir_synth.llm import get_provider, prompt_to_plan

        llm = get_provider(provider)
        plan = prompt_to_plan(llm, prompt_text)

        plan.to_yaml(out)
        typer.echo(f"✓ Generated config: {out}")

    except ImportError:
        typer.echo(
            "Error: LLM support not installed. Install with: pip install fhir-synth[llm]",
            err=True,
        )
        sys.exit(1)


@app.command()
def generate(
    config: str = typer.Option(..., "--config", "-c", help="Configuration file (YAML or JSON)"),
    output: str = typer.Option("./output", "--output", "-o", help="Output directory"),
    format: str | None = typer.Option(None, "--format", help="Output format (overrides config)"),
    seed: int | None = typer.Option(None, "--seed", help="Random seed (overrides config)"),
) -> None:
    """Generate synthetic FHIR dataset from config."""
    # Load plan
    config_path = Path(config)
    if config_path.suffix in [".yaml", ".yml"]:
        plan = DatasetPlan.from_yaml(str(config_path))
    elif config_path.suffix == ".json":
        plan = DatasetPlan.from_json(str(config_path))
    else:
        typer.echo(f"Error: Unknown config format: {config_path.suffix}", err=True)
        sys.exit(1)

    # Apply overrides
    if seed is not None:
        plan.seed = seed
    if format is not None:
        plan.outputs.format = format  # type: ignore[assignment]
    if output:
        plan.outputs.path = output

    typer.echo(f"Generating dataset with seed={plan.seed}...")
    typer.echo(f"  Persons: {plan.population.persons}")
    typer.echo(f"  Time horizon: {plan.time.horizon}")
    typer.echo(f"  Output: {plan.outputs.path} ({plan.outputs.format})")

    # Generate
    generator = DatasetGenerator(plan)
    graph = generator.generate()

    typer.echo(f"\nGenerated {len(graph.resources)} resources:")
    for resource_type in sorted(graph.by_type.keys()):
        count = len(graph.by_type[resource_type])
        typer.echo(f"  {resource_type}: {count}")

    # Validate
    typer.echo("\nValidating...")
    validation_result = validate_dataset(graph, plan)

    if validation_result.is_valid:
        typer.echo("✓ Validation passed")
    else:
        typer.echo("✗ Validation failed:")
        typer.echo(validation_result.summary())
        if validation_result.errors:
            sys.exit(1)

    # Write output
    typer.echo(f"\nWriting output to {plan.outputs.path}...")
    write_output(graph, plan)

    typer.echo("✓ Done")


@app.command()
def validate(
    input: str = typer.Option(
        ..., "--input", "-i", help="Input directory containing NDJSON or Bundle files"
    ),
    config: str | None = typer.Option(
        None, "--config", "-c", help="Optional config file for validation rules"
    ),
) -> None:
    """Validate reference integrity and constraints in generated data."""
    typer.echo("Note: Validation from files not yet implemented.")
    typer.echo("Use 'generate' command which includes validation.")
    sys.exit(1)


def _create_minimal_config(output_path: Path) -> None:
    """Create a minimal example config."""
    from fhir_synth.plan import (
        DatasetPlan,
        OutputConfig,
        PopulationConfig,
        TimeConfig,
        TimeHorizon,
    )

    plan = DatasetPlan(
        version=1,
        seed=42,
        population=PopulationConfig(persons=10),
        time=TimeConfig(horizon=TimeHorizon(years=1)),
        outputs=OutputConfig(format="ndjson", path="./output"),
    )

    plan.to_yaml(str(output_path / "minimal.yml"))


def _create_full_config(output_path: Path) -> None:
    """Create a full example config."""
    config_yaml = """version: 1
seed: 42
population:
  persons: 50
time:
  horizon:
    years: 3
  timezone: "UTC"
resources:
  include:
    - Person
    - Patient
    - Organization
    - Practitioner
    - Location
    - Encounter
    - Observation
    - Condition
    - Procedure
    - AllergyIntolerance
    - MedicationRequest
    - MedicationDispense
    - CarePlan
    - DocumentReference
    - Binary
scenarios:
  - name: "diabetes_management"
    weight: 0.6
  - name: "wellness"
    weight: 0.4
outputs:
  format: "ndjson"
  path: "./output"
  ndjson:
    split_by_resource_type: false
validation:
  enforce_reference_integrity: true
  enforce_timeline_rules: true
  med_dispense_after_request: true
  documentreference_binary_linked: true
"""

    (output_path / "full.yml").write_text(config_yaml)


def _create_multi_org_config(output_path: Path) -> None:
    """Create multi-org example config."""
    config_yaml = """version: 1
seed: 42
population:
  persons: 50
  sources:
    - id: "baylor"
      organization:
        name: "Baylor Health"
        identifiers:
          - system: "urn:org"
            value: "baylor"
      patient_id_namespace: "baylor"
      weight: 0.5
    - id: "sutter"
      organization:
        name: "Sutter Health"
        identifiers:
          - system: "urn:org"
            value: "sutter"
      patient_id_namespace: "sutter"
      weight: 0.5
  person_appearance:
    systems_per_person_distribution:
      1: 0.70
      2: 0.25
      3: 0.05
time:
  horizon:
    years: 3
  timezone: "UTC"
outputs:
  format: "ndjson"
  path: "./output"
  ndjson:
    split_by_resource_type: true
validation:
  enforce_reference_integrity: true
  enforce_timeline_rules: true
"""

    (output_path / "multi-org.yml").write_text(config_yaml)


if __name__ == "__main__":
    app()
