# FHIR Synth

Dynamic FHIR R4B synthetic data generator using LLM-powered code generation and declarative rules.

Generate realistic synthetic healthcare data from natural language prompts. Tell it what you want, and it generates the code to create it.

## What It Does

```
Your Prompt
    ↓
Rules / Code Generation (LLM via LiteLLM)
    ↓
FHIR Resources (Patient, Condition, Observation, etc.)
    ↓
FHIR R4B Bundles (JSON + NDJSON)
```

## Install

```bash
pip install fhir-synth
```

## Quick Start

### 1. Set up your LLM provider

```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

### 2. Generate data from a prompt

Describe what you need in plain English → get a valid FHIR R4B Bundle:

```bash
# 10 diabetic patients with labs (uses gpt-4 by default)
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.json

# 5 patients with hypertension, encounters, and meds
fhir-synth generate "5 patients with hypertension, office encounters, and antihypertensive medications" -o hypertension.json

# Save the generated code for inspection
fhir-synth generate "20 patients with conditions and observations" -o data.json --save-code generated.py

# Split output into one JSON file per patient
fhir-synth generate "10 diabetic patients" --split -o patients/

# Apply custom metadata (security labels, tags, profiles)
fhir-synth generate "10 patients" --meta-config examples/meta-normal.yaml -o output.json

# EMPI: Person → Patients across EMR systems
fhir-synth generate "EMPI dataset" --empi --persons 3 -o empi.json

# AWS Bedrock provider with named profile
fhir-synth generate "5 patients" \
  --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --aws-profile my-profile --aws-region us-east-1 -o output.json

# Try without an API key (mock LLM for testing)
fhir-synth generate "5 patients" --provider mock -o test.json
```

**What happens under the hood:**
1. Your prompt goes to the LLM (via [LiteLLM](https://docs.litellm.ai/) — 100+ providers)
2. LLM generates Python code using `fhir.resources` (Pydantic FHIR models)
3. Code is executed in a sandbox
4. If it fails, the error is sent back to the LLM for self-healing (up to 2 retries)
5. Resources are split by patient and saved as a FHIR R4B Bundle (JSON) + NDJSON

### Output Modes

| Mode | Flag | Output |
|------|------|--------|
| **Bundle** (default) | — | Single JSON bundle + `.ndjson` sidecar |
| **Split** | `--split` | One JSON file per patient + `all_patients.ndjson` |

## CLI Reference

### `fhir-synth generate` — primary command
End-to-end: prompt → LLM → code → execute → FHIR Bundle.

| Flag | Default | Description |
|------|---------|-------------|
| `-o / --out` | `output.json` | Output file (or directory with `--split`) |
| `-p / --provider` | `gpt-4` | LLM model/provider |
| `-t / --type` | `transaction` | Bundle type |
| `--save-code` | — | Save generated Python code |
| `--split` | off | One JSON file per patient (default: single bundle) |
| `--meta-config` | — | YAML file with metadata configuration |
| `--empi` | off | Include EMPI Person→Patient linkage |
| `--persons` | `1` | Number of Persons (EMPI) |
| `--systems` | `emr1,emr2` | EMR system ids (EMPI) |
| `--no-orgs` | off | Skip Organization resources (EMPI) |
| `--aws-profile` | — | AWS profile for Bedrock (`~/.aws/credentials`) |
| `--aws-region` | — | AWS region for Bedrock (e.g. `us-east-1`) |

### `fhir-synth rules`
Generate structured rule definitions from natural language.

```bash
fhir-synth rules "100 diabetic patients with insulin therapy" --out rules.json --provider gpt-4
```

### `fhir-synth codegen`
Generate executable Python code from prompts (without bundling).

```bash
fhir-synth codegen "Create 50 patients" --out code.py
fhir-synth codegen "Create 50 patients" --out code.py --execute
```

### `fhir-synth bundle`
Create FHIR R4B Bundles from NDJSON data or EMPI defaults.

```bash
fhir-synth bundle --resources data.ndjson --out bundle.json --type transaction
fhir-synth bundle --empi --persons 5 --systems emr1,emr2,emr3 --no-orgs --out empi_bundle.json
```

## Python API

```python
from fhir_synth.llm import get_provider
from fhir_synth.code_generator import CodeGenerator
from fhir_synth.rule_engine import RuleEngine, Rule, RuleSet, MetaConfig
from fhir_synth.bundle import (
    BundleBuilder, BundleManager, BundleFactory,
    split_resources_by_patient, write_ndjson, write_split_bundles,
)
from fhir_synth.fhir_utils import FHIRResourceFactory

# --- Generate code from prompts ---
llm = get_provider("mock")
code_gen = CodeGenerator(llm)
code = code_gen.generate_code_from_prompt("Create 20 patients")
resources = code_gen.execute_generated_code(code)

# --- Build a bundle ---
builder = BundleBuilder(bundle_type="transaction")
builder.add_resources(resources)
bundle = builder.build()

# --- Split by patient and write NDJSON ---
per_patient = split_resources_by_patient(resources)
write_ndjson(per_patient, "all_patients.ndjson")

# --- Rule-based generation with custom metadata ---
engine = RuleEngine()
engine.register_ruleset(
    RuleSet(
        resource_type="Patient",
        description="Diabetic patients",
        global_meta=MetaConfig(
            tag=[{"system": "http://example.org/tags", "code": "synthetic"}],
            source="http://example.org/fhir-synth",
        ),
        rules=[
            Rule(
                name="type_2",
                description="Type 2 diabetes",
                conditions={"type": 2},
                actions={"resourceType": "Patient", "id": "p1"},
                weight=1.0,
                meta=MetaConfig(
                    security=[{
                        "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                        "code": "N",
                        "display": "Normal",
                    }],
                    profile=["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"],
                ),
            )
        ],
    )
)

# --- Create FHIR resources directly ---
patient = FHIRResourceFactory.create_patient("p1", "Jane", "Doe", "1990-01-01")

# --- AWS Bedrock ---
llm = get_provider(
    "bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    aws_profile="my-profile",
    aws_region="us-east-1",
)
```

## Custom Metadata

Add security labels, tags, profiles, and other FHIR metadata to your generated resources using a YAML configuration file:

**meta-normal.yaml:**
```yaml
meta:
  security:
    - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
      code: "N"
      display: "Normal"
  tag:
    - system: "http://example.org/tags"
      code: "synthetic-data"
      display: "Synthetic Test Data"
  profile:
    - "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
  source: "http://example.org/fhir-synth"
```

**Usage:**
```bash
# Single bundle with metadata
fhir-synth generate "10 patients" --meta-config examples/meta-normal.yaml -o output.json

# Split per-patient files with metadata
fhir-synth generate "10 diabetic patients" --meta-config examples/meta-normal.yaml --split -o patients/
```

**Supported metadata fields:**
- `security` — Security labels (confidentiality, sensitivity, etc.)
- `tag` — Tags for operational/workflow purposes
- `profile` — Profile URLs the resource conforms to
- `source` — Source system URI

**Example configs:**
- [`examples/meta-normal.yaml`](examples/meta-normal.yaml) — Normal confidentiality, synthetic data tags
- [`examples/meta-restricted.yaml`](examples/meta-restricted.yaml) — Restricted security for sensitive data

See the [Metadata Quick Reference](docs/guide/metadata-reference.md) for the full schema.

## LLM Providers

The `generate` command defaults to `gpt-4`. Set your API key in a `.env` file:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Supported via [LiteLLM](https://docs.litellm.ai/): OpenAI, Anthropic, AWS Bedrock, Azure, Google Gemini, and 100+ providers.

| Provider | `--provider` value | Auth |
|----------|-------------------|------|
| OpenAI | `gpt-4`, `gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `claude-3-opus-20240229` | `ANTHROPIC_API_KEY` |
| AWS Bedrock | `bedrock/anthropic.claude-v2` | `--aws-profile` / `--aws-region` |
| Google Gemini | `gemini/gemini-pro` | `GEMINI_API_KEY` |
| Azure | `azure/gpt-4` | `AZURE_API_KEY` |
| Mock (testing) | `mock` | None |

Use `--provider mock` for testing without an API key.

## Architecture

FHIR Synth is organized into focused packages:

- **`bundle/`** — Bundle creation and management (`BundleBuilder`, `BundleManager`, `BundleFactory`, `split_resources_by_patient`, `write_ndjson`, `write_split_bundles`)
- **`code_generator/`** — LLM-powered code generation with self-healing execution (`CodeGenerator`, `PromptToRulesConverter`)
- **`rule_engine/`** — Declarative rule engine, EMPI logic, and metadata models (`RuleEngine`, `RuleSet`, `Rule`, `MetaConfig`)
- **`fhir_utils/`** — FHIR resource factory and lazy resource class map (`FHIRResourceFactory`)
- **`llm.py`** — Unified LLM provider interface via LiteLLM (`LLMProvider`, `get_provider`)
- **`cli.py`** — Typer-based CLI

See [Architecture](docs/architecture.md) for complete system design and data flows.

## CI/CD

The project uses GitHub Actions with three chained workflows:

- **CI** (`ci.yml`) — Runs on every push/PR: lint (`ruff`, `mypy`) + tests (`pytest`)
- **Release** (`release.yml`) — Triggered after CI passes on `main`: auto-increments version and creates a GitHub Release
- **Docs** (`docs.yml`) — Triggered after Release: builds and deploys MkDocs to GitHub Pages

## Development

```bash
# Install dev dependencies
hatch env create

# Run tests
hatch run test

# Type checking & linting
hatch run check

# Format
hatch run format

# Serve docs locally
hatch run docs:serve
```

## License

MIT

