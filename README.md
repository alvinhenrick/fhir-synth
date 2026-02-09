# FHIR Synth

Deterministic FHIR R4 synthetic data generator with LLM-assisted planning and multi-organization support.

## Project Status

🚀 **Alpha Release** - Feature-complete and actively developed. All core functionality works; additional optimizations and providers coming in upcoming releases.

## Overview

FHIR Synth generates realistic, reproducible synthetic healthcare data for testing and development. It's perfect for:
- **EMPI/Master Patient Index testing** - Generate Person entities linked to multiple source system Patient records
- **Integration testing** - Ensure FHIR compliance and reference integrity
- **Performance testing** - Bulk load data in configurable volumes
- **System validation** - Test complex healthcare workflows with realistic timelines

## Features

- **Deterministic generation**: Same seed + config → same output (reproducible testing)
- **Multi-org patient resolution**: Generate Person entities with Patient records across multiple source systems
- **Reference integrity**: All FHIR references guaranteed to resolve
- **Timeline plausibility**: Events occur in realistic order within configurable time horizons
- **LLM-assisted planning**: Convert natural language to configurations (OpenAI, Anthropic, Bedrock, or mock)
- **Multiple output formats**: NDJSON (default), FHIR Bundles, or individual JSON files
- **Type-safe configuration**: Pydantic models with validation
- **Full test coverage**: Comprehensive test suite with mypy type checking

## Supported FHIR Resources

| Category | Resources |
|----------|-----------|
| **Base** | Person, Patient, Organization, Practitioner, Location |
| **Clinical** | Encounter, Condition, Observation, Procedure, AllergyIntolerance, CarePlan |
| **Medications** | Medication, MedicationRequest, MedicationDispense |
| **Documents** | DocumentReference, Binary |

## Installation

```bash
# Basic installation
pip install fhir-synth

# With LLM support (OpenAI, Anthropic, AWS Bedrock)
pip install fhir-synth[llm]

# Development (includes testing & type checking)
git clone <repo>
cd fhir-synth
pip install -e ".[dev]"

# With everything
pip install -e ".[dev,llm]"
```

## Quick Start

### 1. Setup (Optional: API Keys for LLM)

If you want to use LLM-assisted config generation, set up your API keys:

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your API keys (or just use mock provider)
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
```

> **Note**: The project includes a `mock` LLM provider for testing without any API keys!

### 2. Generate from a Natural Language Prompt

```bash
# Using built-in mock LLM (no API key required)
fhir-synth prompt "50 patients with diabetes across Baylor and Sutter health systems" --out config.yml

# Using OpenAI (API key from .env or OPENAI_API_KEY env var)
fhir-synth prompt "100 patients with various conditions" --out config.yml --provider gpt-4

# Then generate data from the created config
fhir-synth generate -c config.yml -o ./output --seed 42
```

### 3. Generate from Configuration File

```bash
# Initialize sample configs
fhir-synth init

# Generate from minimal config (10 patients, 1 year)
fhir-synth generate -c examples/minimal.yml -o ./output --seed 42

# Generate multi-org data for EMPI testing
fhir-synth generate -c examples/multi-org.yml -o ./output --format ndjson

# Validate the output
fhir-synth validate -i ./output
```

## CLI Commands

### `fhir-synth init` - Create Example Configurations

Create template configuration files for different scenarios.

```bash
# Create all example configs (default)
fhir-synth init

# Create specific examples
fhir-synth init --minimal              # Basic config
fhir-synth init --full                 # All resource types
fhir-synth init --multi-org            # Multi-org setup

# Save to custom directory
fhir-synth init --output ./configs
```

### `fhir-synth prompt` - Generate Config from Text

Convert natural language to a validated YAML configuration using an LLM. API keys are automatically loaded from `.env` file or environment variables.

```bash
# Mock LLM (no API key needed)
fhir-synth prompt "50 diabetes patients" --out config.yml

# OpenAI (requires OPENAI_API_KEY in .env or environment)
fhir-synth prompt "pediatric asthma patients" --out config.yml --provider gpt-4

# Anthropic (requires ANTHROPIC_API_KEY in .env or environment)
fhir-synth prompt "ICU patients" --out config.yml --provider claude-3-opus

# AWS Bedrock
fhir-synth prompt "chronic disease cohort" --out config.yml --provider bedrock/anthropic.claude-v2
```

**API Key Setup:**
1. Copy `.env.example` to `.env` in your project root
2. Add your API key(s) to `.env`
3. The CLI will automatically load them

**Options:**
- `PROMPT_TEXT` - Description of dataset to generate
- `--out, -o PATH` - Output config file path (required)
- `--provider` - LLM provider: `mock` (default), `gpt-4`, `claude-3-opus`, `bedrock/...`, etc.

### `fhir-synth generate` - Create Synthetic Data

Generate FHIR dataset from a configuration file.

```bash
# Basic generation
fhir-synth generate --config config.yml

# With custom output directory
fhir-synth generate --config config.yml --output ./my_data

# Override output format
fhir-synth generate --config config.yml --format bundle

# Override random seed (for reproducibility)
fhir-synth generate --config config.yml --seed 12345

# Combine multiple options
fhir-synth generate \
  --config examples/multi-org.yml \
  --output ./synthetic \
  --format ndjson \
  --seed 999
```

**Options:**
- `--config, -c PATH` - Configuration file (YAML/JSON) (required)
- `--output, -o DIR` - Output directory (default: `./output`)
- `--format` - Format: `ndjson` (default), `bundle`, or `files`
- `--seed` - Random seed for reproducibility (overrides config)

### `fhir-synth validate` - Check Generated Data

Validate reference integrity and constraints.

```bash
# Validate generated data
fhir-synth validate --input ./output

# With custom validation rules
fhir-synth validate --input ./output --config validation.yml
```

**Options:**
- `--input, -i PATH` - Input directory (required)
- `--config, -c PATH` - Optional validation rules config

## Configuration Guide

### Minimal Configuration

```yaml
version: 1
seed: 42
population:
  persons: 10

time:
  horizon:
    years: 1
  timezone: "UTC"

outputs:
  format: "ndjson"
  path: "./output"
```

### Multi-Organization Configuration (EMPI Use Case)

Perfect for testing master patient index and record linkage systems.

```yaml
version: 1
seed: 42

population:
  persons: 50

  # Define multiple source systems
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

  # How many source systems each person appears in
  person_appearance:
    systems_per_person_distribution:
      1: 0.70   # 70% in only 1 system
      2: 0.25   # 25% in 2 systems
      3: 0.05   # 5% in 3 systems

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
  med_dispense_after_request: true
```

### Configuration Schema

| Field | Type | Description |
|-------|------|-------------|
| `version` | int | Schema version (currently 1) |
| `seed` | int | Random seed for deterministic output |
| `population.persons` | int | Number of Person entities to generate |
| `population.sources` | array | Source systems (for multi-org) |
| `time.horizon` | object | Time period: `{years: N}`, `{months: N}`, or `{days: N}` |
| `time.timezone` | string | Timezone (default: "UTC") |
| `outputs.format` | string | `ndjson` (default), `bundle`, or `files` |
| `outputs.path` | string | Output directory path |
| `validation.*` | bool | Validation rules to enforce |

## Multi-Organization Use Case

### What Gets Generated

1. **Person resources** - Canonical identity records
   - Each Person has unique ID (e.g., `Person-1`)
   - Links to one or more Patient records via `Person.link.target`

2. **Patient resources** - Source-system-specific records
   - Namespaced IDs (e.g., `baylor-Patient-1`, `sutter-Patient-2`)
   - Each has `managingOrganization` pointing to source org
   - Clinical data (Encounters, Observations, Meds) attached to these records

3. **Organization resources** - One per source system
   - Identifiers matching your source system config
   - Referenced by Patient.managingOrganization

### Example Use Cases

- **EMPI Resolution**: Load Patients from multiple sources and verify correct Person linkage
- **Data Quality Testing**: Simulate fuzzy matching scenarios
- **Source Integration**: Test workflows pulling from multiple healthcare systems
- **Deduplication**: Validate algorithms identifying duplicate patient records

## Development

### Setup

```bash
# Clone and setup with development dependencies
git clone <repo>
cd fhir-synth
pip install -e ".[dev]"

# Create .env for local testing (if needed)
cp .env.example .env
```

### Code Quality

This project uses **Ruff** (linting/formatting) and **mypy** (type checking). Run these via hatch:

```bash
# Run all checks (lint + type checking)
hatch run check

# Format code automatically
hatch run format

# Fix linting issues automatically
hatch run lint
```

### Testing

```bash
# Run all tests
hatch run test

# Run with coverage report
hatch run cov

# Fast parallel testing
hatch run test-fast

# Run specific test file
pytest tests/test_generator.py

# Run with verbose output
pytest -v tests/
```

### Useful Commands

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Fast parallel tests
pytest -n auto tests/

# Type checking
mypy src

# Linting
ruff check src tests

# Format code
ruff format src tests
```

## Architecture

- **Plan schema**: Pydantic models for type-safe configuration
- **Multi-org support**: Person entities link to Patient records from different sources
- **Deterministic RNG**: Seeded random generation for reproducible datasets
- **Graph-based generation**: Internal entity graph ensures reference integrity
- **Pluggable LLM providers**: OpenAI, Anthropic, Bedrock, or mock
- **Type-safe**: Full mypy type checking support

## License

MIT

