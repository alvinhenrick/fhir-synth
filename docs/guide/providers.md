# LLM Providers

FHIR Synth uses [LiteLLM](https://docs.litellm.ai/) to support 100+ LLM providers.

## Supported Providers

| Provider | Model Example | Auth |
|----------|---------------|------|
| OpenAI | `gpt-4`, `gpt-4o` | `OPENAI_API_KEY` env var |
| Anthropic | `claude-3-opus-20240229` | `ANTHROPIC_API_KEY` env var |
| AWS Bedrock | `bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0` | AWS profile / env vars |
| Azure OpenAI | `azure/gpt-4` | `AZURE_API_KEY` env var |
| Google | `gemini/gemini-pro` | `GEMINI_API_KEY` env var |

See [LiteLLM docs](https://docs.litellm.ai/docs/providers) for the full list.

## OpenAI / Anthropic / Google

Set your API key in a `.env` file or export it:

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

```bash
# OpenAI GPT-4 (default)
fhir-synth generate "10 patients" -o output.json

# Anthropic Claude
fhir-synth generate "10 patients" -p claude-3-opus-20240229 -o output.json
```

## AWS Bedrock

Bedrock uses your existing AWS credentials instead of API keys.
Install the optional `bedrock` extra for `boto3` support:

```bash
pip install "fhir-synth[bedrock] @ git+https://github.com/alvinhenrick/fhir-synth.git@main"
```

FHIR Synth supports **four ways** to authenticate:

### Option 1 — `--aws-profile` flag (recommended)

Point to a named profile in `~/.aws/credentials`:

```bash
fhir-synth generate "10 patients" \
  --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --aws-profile my-profile \
  --aws-region us-east-1 \
  -o output.json
```

This reads the `[my-profile]` section from `~/.aws/credentials`:

```ini
# ~/.aws/credentials
[my-profile]
aws_access_key_id = AKIA...
aws_secret_access_key = ...

# ~/.aws/config
[profile my-profile]
region = us-east-1
```

### Option 2 — Environment variables

```bash
export AWS_PROFILE=my-profile          # profile name
export AWS_DEFAULT_REGION=us-east-1    # region

fhir-synth generate "10 patients" \
  --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 \
  -o output.json
```

Or with explicit keys:

```bash
export AWS_ACCESS_KEY_ID=AKIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_REGION_NAME=us-east-1

fhir-synth generate "10 patients" \
  --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 \
  -o output.json
```

### Option 3 — `.env` file

```bash
# .env
AWS_PROFILE=my-profile
AWS_DEFAULT_REGION=us-east-1
```

### Option 4 — SSO profiles

If you use AWS SSO / IAM Identity Center:

```bash
aws sso login --profile my-sso-profile

fhir-synth generate "10 patients" \
  --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --aws-profile my-sso-profile \
  -o output.json
```

### Bedrock Model Names

Use the `bedrock/` prefix followed by the model ID:

| Model | Provider String |
|-------|----------------|
| Claude 3.5 Sonnet v2 | `bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0` |
| Claude 3 Opus | `bedrock/anthropic.claude-3-opus-20240229-v1:0` |
| Claude 3 Haiku | `bedrock/anthropic.claude-3-haiku-20240307-v1:0` |
| Claude 3.5 Haiku | `bedrock/us.anthropic.claude-3-5-haiku-20241022-v1:0` |
| Titan Text | `bedrock/amazon.titan-text-express-v1` |
| Llama 3 | `bedrock/meta.llama3-70b-instruct-v1:0` |

!!! tip "Finding model IDs"
    Run `aws bedrock list-foundation-models --region us-east-1` to see
    available models in your account. The `modelId` value is what you
    append after `bedrock/`.

### Python API with Bedrock

```python
from fhir_synth.llm import get_provider

# With named profile
llm = get_provider(
    "bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    aws_profile="my-profile",
    aws_region="us-east-1",
)

# Or rely on env vars / default profile
llm = get_provider("bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0")
```

### Troubleshooting Bedrock

**`AccessDeniedException`**

Your IAM user / role needs the `bedrock:InvokeModel` permission:

```json
{
  "Effect": "Allow",
  "Action": "bedrock:InvokeModel",
  "Resource": "arn:aws:bedrock:us-east-1::foundation-model/*"
}
```

**`Could not connect to the endpoint`**

Check your region — not all models are available in every region.
Use `--aws-region` to set the correct one.

**`ExpiredTokenException`**

Re-authenticate: `aws sso login --profile my-profile` or refresh
your temporary credentials.

## Mock Provider

The mock provider generates hardcoded sample resources without calling any API:

```bash
fhir-synth generate "5 patients" --provider mock -o test.json
```

Useful for testing, CI/CD pipelines, and development.

