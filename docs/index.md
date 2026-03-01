# FHIR Synth

Dynamic FHIR R4B synthetic data generator using LLM-powered code generation and declarative rules.

Generate realistic synthetic healthcare data from natural language prompts. Tell it what you want, and it generates the code to create it.

## How It Works

```
Your Prompt
    ↓
Rules / Code Generation (LLM)
    ↓
FHIR Resources (Patient, Condition, Observation, etc.)
    ↓
FHIR R4B Bundles
```

## Features

- **Natural Language → FHIR**: Describe what you need in plain English, get valid FHIR R4B Bundles
- **LLM-Powered Code Generation**: Uses GPT-4, Claude, Bedrock, or 100+ providers via [LiteLLM](https://docs.litellm.ai/)
- **Self-Healing Execution**: If generated code fails, errors are sent back to the LLM for automatic retry
- **Declarative Rule Engine**: Define generation rules as structured data
- **EMPI Support**: Generate Person → Patient linkages across EMR systems
- **Custom Metadata**: Add security labels, tags, profiles, and source via YAML config
- **Full FHIR R4B**: Supports all 141 R4B resource types via `fhir.resources` Pydantic models

## Install

```bash
# Install from GitHub (latest release)
pip install git+https://github.com/alvinhenrick/fhir-synth.git@main

# With AWS Bedrock support
pip install "fhir-synth[bedrock] @ git+https://github.com/alvinhenrick/fhir-synth.git@main"
```

## Quick Example

```bash
# Generate 10 diabetic patients with labs
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.ndjson

# Try without an API key (mock LLM for testing)
fhir-synth generate "5 patients" --provider mock -o test.ndjson
```

## Next Steps

- [Installation](getting-started/installation.md) — Set up FHIR Synth
- [Quick Start](getting-started/quickstart.md) — Generate your first data
- [CLI Reference](guide/cli.md) — All commands and flags
- [Architecture](architecture.md) — System design and data flows

