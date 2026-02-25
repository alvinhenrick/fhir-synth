# LLM Providers

FHIR Synth uses [LiteLLM](https://docs.litellm.ai/) to support 100+ LLM providers.

## Supported Providers

| Provider | Model Example | Env Variable |
|----------|---------------|--------------|
| OpenAI | `gpt-4`, `gpt-4o`, `gpt-3.5-turbo` | `OPENAI_API_KEY` |
| Anthropic | `claude-3-opus-20240229` | `ANTHROPIC_API_KEY` |
| AWS Bedrock | `bedrock/anthropic.claude-v2` | AWS credentials |
| Azure OpenAI | `azure/gpt-4` | `AZURE_API_KEY` |
| Google | `gemini/gemini-pro` | `GEMINI_API_KEY` |

See [LiteLLM docs](https://docs.litellm.ai/docs/providers) for the full list.

## Configuration

Set your API key in a `.env` file:

```bash
# OpenAI (default)
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
# OpenAI GPT-4 (default)
fhir-synth generate "10 patients" -o output.json

# Specify provider
fhir-synth generate "10 patients" -p claude-3-opus-20240229 -o output.json

# Mock provider for testing (no API key needed)
fhir-synth generate "5 patients" --provider mock -o test.json
```

## Mock Provider

The mock provider generates hardcoded sample resources without calling any API. Useful for:

- Testing without API keys
- CI/CD pipelines
- Development and debugging

```bash
fhir-synth generate "5 patients" --provider mock -o test.json
```

