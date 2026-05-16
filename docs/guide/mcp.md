# MCP Server

FHIR Synth ships an [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server so Claude (Desktop, Code, or any MCP client) can generate synthetic FHIR data on demand.

## Why

The MCP server returns **both the generated Python code AND the executed FHIR resources**. The script is self-contained — commit it to your repo and call `generate_resources()` from pytest fixtures forever after, with no LLM round-trip for replay.

```
LLM runs once to author the code  →  the code runs forever.
```

## Install

```bash
pip install "fhir-synth[mcp]"
# Or get everything (DSPy two-stage, Bedrock, semantic skills, sandboxes):
pip install "fhir-synth[all]"
```

This adds a `fhir-synth-mcp` console script.

## Tools

The server exposes five tools:

| Tool | Purpose |
| --- | --- |
| `generate_fhir_data` | Prompt → Python code + executed FHIR resources + quality report |
| `validate_fhir_bundle` | Validate any FHIR JSON / Bundle / NDJSON payload (Pydantic + reference integrity + US Core) |
| `list_skills` | Discover the clinical domains the generator knows about |
| `list_runs` | Browse previously generated runs |
| `get_run` | Fetch a run's prompt, code, and resources for replay |

## Configure your LLM provider

The server reads provider settings from environment variables — each user brings their own credentials.

**Anthropic direct:**

```
FHIR_SYNTH_PROVIDER=claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-...
```

**AWS Bedrock:**

```
FHIR_SYNTH_PROVIDER=bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0
AWS_PROFILE=my-profile
AWS_REGION=us-east-1
```

**OpenAI / codex:**

```
FHIR_SYNTH_PROVIDER=gpt-5.2-codex
OPENAI_API_KEY=sk-...
```

Any [LiteLLM](https://docs.litellm.ai/docs/providers) model string works.

## Wire into Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "fhir-synth": {
      "command": "fhir-synth-mcp",
      "env": {
        "FHIR_SYNTH_PROVIDER": "claude-sonnet-4-5",
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

## Wire into Claude Code

`~/.claude/settings.json` (or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "fhir-synth": {
      "command": "fhir-synth-mcp",
      "env": {
        "FHIR_SYNTH_PROVIDER": "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "AWS_PROFILE": "my-profile",
        "AWS_REGION": "us-east-1",
        "FHIR_SYNTH_PIPELINE": "dspy",
        "FHIR_SYNTH_COMPILED": "miprov2"
      }
    }
  }
}
```

Restart Claude. Type something like *"generate 10 diabetic patients with HbA1c labs"* — Claude calls `generate_fhir_data` and you'll get back a `runs/<name>/` directory with the script and NDJSON.

## Bundled compiled DSPy programs

Two pre-optimized [DSPy](pipeline.md) programs ship inside the wheel:

| Short name | What it is | When to pick it |
| --- | --- | --- |
| `miprov2` | MIPROv2-optimized program (default) | Best quality, recommended |
| `bootstrap` | BootstrapFewShot program | Faster, smaller few-shot context |

Enable via env vars:

```
FHIR_SYNTH_PIPELINE=dspy
FHIR_SYNTH_COMPILED=miprov2     # or "bootstrap", or "/path/to/your.json", or "none"
```

Requires `pip install "fhir-synth[mcp,dspy]"`.

Override per call from a prompt — the tool also accepts `pipeline` and `compiled_program` parameters, so a user can say *"regenerate using the bootstrap program"* and Claude will pass `compiled_program="bootstrap"` for that one call without touching the env config.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `FHIR_SYNTH_PROVIDER` | `claude-sonnet-4-5` | LiteLLM model string |
| `ANTHROPIC_API_KEY` | – | Anthropic credentials |
| `OPENAI_API_KEY` | – | OpenAI credentials |
| `AWS_PROFILE` / `AWS_REGION` | – | Bedrock credentials |
| `FHIR_SYNTH_PIPELINE` | `default` | `default` (single-stage) or `dspy` (two-stage) |
| `FHIR_SYNTH_COMPILED` | `miprov2` | Bundled short name, filesystem path, or `none` |
| `FHIR_SYNTH_EXECUTOR` | `local` | `local`, `docker`, `e2b`, `blaxel` |
| `FHIR_SYNTH_RUNS_DIR` | `runs` | Where run artefacts are written |

## Replaying generated code without the LLM

The killer feature: every `generate_fhir_data` call writes a self-contained Python script. Drop it into your repo and your tests no longer need an LLM round-trip:

```python
# conftest.py
from runs.brave_phoenix.brave_phoenix import generate_resources

import pytest

@pytest.fixture(scope="session")
def fhir_patients():
    return generate_resources()   # pure Python, deterministic, no API call
```

## Troubleshooting

### "The DSPy pipeline requires the optional dspy extra"

You set `FHIR_SYNTH_PIPELINE=dspy` but installed `[mcp]` only. Install with both:

```bash
pip install "fhir-synth[mcp,dspy]"
```

### `AuthenticationError` from LiteLLM

The provider-appropriate env var isn't set or isn't visible to the MCP process. Confirm with:

```bash
echo "$ANTHROPIC_API_KEY" | head -c 10
```

Then re-launch your Claude client so it picks up the env.

### Compiled program version warnings

```
WARNING dspy.primitives.base_module: There is a mismatch of dspy version between
saved model and current environment.
```

This is informational — the bundled `miprov2.json` was compiled against a slightly older DSPy version. Quality is unaffected; suppress by re-running `fhir-synth optimize` against your current DSPy and pointing `FHIR_SYNTH_COMPILED` at the result.
