# Installation

## Requirements

- Python 3.12 or higher
- An LLM API key (OpenAI, Anthropic, etc.) — or use `--provider mock` for testing

## Install from GitHub

FHIR Synth is distributed via GitHub Releases (not PyPI). Install directly from the repository:

```bash
# Latest release (main branch)
pip install git+https://github.com/alvinhenrick/fhir-synth.git@main

# Specific version tag
pip install git+https://github.com/alvinhenrick/fhir-synth.git@v1.0.0
```

### With AWS Bedrock Support

To use AWS Bedrock as your LLM provider, install the `bedrock` extra:

```bash
pip install "fhir-synth[bedrock] @ git+https://github.com/alvinhenrick/fhir-synth.git@main"
```

## Install from Source (Development)

```bash
git clone https://github.com/alvinhenrick/fhir-synth.git
cd fhir-synth
pip install -e ".[dev]"
```

## Set Up Your LLM Provider

Create a `.env` file in your project root with your API key:

```bash
# OpenAI (default provider)
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google Gemini
GEMINI_API_KEY=...

# Azure OpenAI
AZURE_API_KEY=...
AZURE_API_BASE=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-02-01
```

### AWS Bedrock

Bedrock uses your existing AWS credentials instead of API keys.
Configure a named profile in `~/.aws/credentials`:

```ini
# ~/.aws/credentials
[my-profile]
aws_access_key_id = AKIA...
aws_secret_access_key = ...

# ~/.aws/config
[profile my-profile]
region = us-east-1
```

Then pass the profile via CLI flags or environment variables:

```bash
# CLI flags
fhir-synth generate "10 patients" \
  --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --aws-profile my-profile --aws-region us-east-1 -o output.json

# Or environment variables
export AWS_PROFILE=my-profile
export AWS_DEFAULT_REGION=us-east-1
```

See [LLM Providers](../guide/providers.md) for full details on all supported providers.

!!! tip "No API Key?"
    Use `--provider mock` to test without any API key. The mock provider returns hardcoded sample resources.

## Verify Installation

```bash
fhir-synth --help
```

You should see the available commands: `generate`, `rules`, `codegen`, `bundle`.

