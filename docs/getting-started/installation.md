# Installation

## Requirements

- Python 3.12 or higher
- An LLM API key (OpenAI, Anthropic, etc.) — or use `--provider mock` for testing

## Install from GitHub

```bash
pip install git+https://github.com/alvinhenrick/fhir-synth.git
```

## Optional Extras

```bash
# AWS Bedrock support (requires boto3)
pip install "fhir-synth[bedrock] @ git+https://github.com/alvinhenrick/fhir-synth.git@main"

# DSPy two-stage pipeline (clinical planning → code synthesis)
pip install "fhir-synth[dspy] @ git+https://github.com/alvinhenrick/fhir-synth.git@main"

# FAISS semantic skill selection
pip install "fhir-synth[semantic] @ git+https://github.com/alvinhenrick/fhir-synth.git@main"

# Docker sandbox executor
pip install "fhir-synth[docker] @ git+https://github.com/alvinhenrick/fhir-synth.git@main"

# E2B cloud sandbox executor
pip install "fhir-synth[e2b] @ git+https://github.com/alvinhenrick/fhir-synth.git@main"
```

## Install from Source

```bash
git clone https://github.com/alvinhenrick/fhir-synth.git
cd fhir-synth
pip install -e ".[dev]"
```

## Set Up Your LLM Provider

Create a `.env` file in your project root with your API key:

```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Or any provider supported by LiteLLM
```

!!! tip "No API Key?"
    Use `--provider mock` to test without any API key. The mock provider returns hardcoded sample resources.

## Verify Installation

```bash
fhir-synth --help
```

You should see the available commands: `generate`, `codegen`, `bundle`.

