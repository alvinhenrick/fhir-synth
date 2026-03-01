# Installation

## Requirements

- Python 3.12 or higher
- An LLM API key (OpenAI, Anthropic, etc.) — or use `--provider mock` for testing

## Install from GitHub

```bash
pip install git+https://github.com/alvinhenrick/fhir-synth.git
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

You should see the available commands: `generate`, `rules`, `codegen`, `bundle`.

