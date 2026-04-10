# FHIR Synth

Dynamic FHIR synthetic data generator using LLM-powered code generation and declarative rules (supports R4B, STU3).

Generate realistic synthetic healthcare data from natural language prompts. Tell it what you want, and it generates the code to create it.

> *Inspired by [Synthea](https://github.com/synthetichealth/synthea). Created and designed by human. Code guided by AI, for AI.*

## How It Works

```
Your Prompt
    ↓
Skills Selection (keyword fuzzy matching / FAISS semantic)
    ↓
Code Generation (LLM via LiteLLM)          ── or ── DSPy Two-Stage Pipeline
    ↓                                                  Stage 1: Clinical Plan
FHIR Resources (Patient, Condition, etc.)              Stage 2: Code Synthesis
    ↓
FHIR Validation + Reference Integrity + US Core
    ↓
FHIR Bundles (JSON + NDJSON) — R4B or STU3
```

## Features

- **Natural Language → FHIR**: Describe what you need in plain English, get valid FHIR Bundles (R4B or STU3)
- **Two-Stage Pipeline (DSPy)**: Optional clinical planning → code synthesis pipeline with [DSPy](https://dspy.ai/) for structured output and prompt optimization
- **Skills System**: 16 built-in domain skills with fuzzy keyword matching (typo-tolerant) for realistic data
- **LLM-Powered Code Generation**: Uses GPT-4, Claude, Bedrock, or 100+ providers via [LiteLLM](https://docs.litellm.ai/)
- **Self-Healing Execution**: If generated code fails, errors are sent back to the LLM for automatic retry (up to 2 retries)
- **Enhanced FHIR Validation**: Offline validation using `fhir.resources` Pydantic models — required fields, choice-type [x] checks, reference integrity, and US Core compliance
- **Pluggable Executor Backends**: Local interpreter (default), Docker, E2B, or Blaxel cloud sandboxes via [smolagents](https://huggingface.co/docs/smolagents)
- **Faker Integration**: Uses [Faker](https://faker.readthedocs.io/) for realistic demographic and clinical data
- **EMPI Support**: Generate Person → Patient linkages across EMR systems
- **Custom Metadata**: Add security labels, tags, profiles, and source via YAML config
- **Multi-Version Support**: R4B (default) and STU3 via `--fhir-version` flag (case-insensitive)

## Install

```bash
# Install from GitHub (latest release)
pip install git+https://github.com/alvinhenrick/fhir-synth.git@main

# With AWS Bedrock support
pip install "fhir-synth[bedrock] @ git+https://github.com/alvinhenrick/fhir-synth.git@main"
```

## Quick Example

```bash
# Generate 10 diabetic patients with labs (R4B by default)
# → runs/brave_phoenix/ with prompt.txt, .py, .ndjson
fhir-synth generate "10 diabetic patients with HbA1c observations"

# Generate STU3 resources instead
fhir-synth generate "10 patients with diabetes" --fhir-version stu3

# Try without an API key (mock LLM for testing)
fhir-synth generate "5 patients" --provider mock
```

## Next Steps

- [Installation](getting-started/installation.md) — Set up FHIR Synth
- [Quick Start](getting-started/quickstart.md) — Generate your first data
- [Skills System](guide/skills.md) — Learn about built-in skills and create custom ones
- [CLI Reference](guide/cli.md) — All commands and flags
- [DSPy Pipeline](guide/pipeline.md) — Two-stage clinical planning with DSPy optimization
- [Architecture](architecture.md) — System design and data flows

