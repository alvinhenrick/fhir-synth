# FHIR Synth

Dynamic FHIR R4B synthetic data generator using LLM-powered code generation and declarative rules.

Generate realistic synthetic healthcare data from natural language prompts. Tell it what you want, and it generates the code to create it.

## What It Does

```
Your Prompt
    ↓
Rules / Code Generation (LLM)
    ↓
FHIR Resources (Patient, Condition, Observation, etc.)
    ↓
FHIR R4B Bundles
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

# EMPI: Person → Patients across EMR systems
fhir-synth generate "EMPI dataset" --empi --persons 3 -o empi.json

# Try without an API key (mock LLM for testing)
fhir-synth generate "5 patients" --provider mock -o test.json
```

**What happens under the hood:**
1. Your prompt goes to the LLM
2. LLM generates Python code using `fhir.resources` (Pydantic FHIR models)
3. Code is executed in a sandbox
4. If it fails, the error is sent back to the LLM for self-healing (up to 2 retries)
5. Resources are wrapped in a FHIR R4B Bundle and saved

## CLI Reference

### `fhir-synth generate` — primary command
End-to-end: prompt → LLM → code → execute → FHIR Bundle.

| Flag | Default | Description |
|------|---------|-------------|
| `-o / --out` | `output.json` | Output file |
| `-p / --provider` | `gpt-4` | LLM model/provider |
| `-t / --type` | `transaction` | Bundle type |
| `--save-code` | — | Save generated Python code |
| `--empi` | off | Include EMPI Person→Patient linkage |
| `--persons` | `1` | Number of Persons (EMPI) |
| `--systems` | `emr1,emr2` | EMR system ids (EMPI) |
| `--no-orgs` | off | Skip Organization resources (EMPI) |
| `--security` | — | Add security label (format: `system\|code\|display`) |
| `--tag` | — | Add tag (format: `system\|code\|display`) |
| `--profile` | — | Add profile URL |
| `--source` | — | Add source system URI |

**Examples with metadata:**
```bash
# Add security label to all resources
fhir-synth generate "10 patients" \
  --security "http://terminology.hl7.org/CodeSystem/v3-Confidentiality|R|Restricted" \
  -o restricted.json

# Add multiple metadata elements
fhir-synth generate "5 diabetic patients with labs" \
  --tag "http://example.org/tags|synthetic|Synthetic Data" \
  --profile "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient" \
  --source "http://example.org/fhir-synth" \
  -o tagged.json
```

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
from fhir_synth.bundle import BundleBuilder, BundleManager
from fhir_synth.fhir_utils import FHIRResourceFactory

# Generate code from prompts
llm = get_provider("mock")
code_gen = CodeGenerator(llm)
code = code_gen.generate_code_from_prompt("Create 20 patients")
resources = code_gen.execute_generated_code(code)

# Use rule-based generation with custom metadata
engine = RuleEngine()
engine.register_ruleset(
    RuleSet(
        resource_type="Patient",
        description="Diabetic patients",
        # Global metadata applied to all Patient resources
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
                # Rule-specific metadata (merged with global_meta)
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

# Create FHIR resources directly
patient = FHIRResourceFactory.create_patient("p1", "Jane", "Doe", "1990-01-01")

# Build bundles
builder = BundleBuilder(bundle_type="transaction")
builder.add_resources(resources)
bundle = builder.build()
```

## Custom Metadata

Add security labels, tags, profiles, and other FHIR metadata to your generated resources using a YAML configuration file:

**metadata.yaml:**
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
fhir-synth generate "20 patients with conditions" \
  --meta-config metadata.yaml \
  -o output.json
```

**Supported metadata fields:**
- `security` — Security labels (confidentiality, sensitivity, etc.)
- `tag` — Tags for operational/workflow purposes
- `profile` — Profile URLs the resource conforms to
- `source` — Source system URI

**Example configs:**
- `examples/metadata.yaml` - Normal confidentiality, synthetic data tags
- `examples/metadata-restricted.yaml` - Restricted security for sensitive data

See [examples/metadata_example.yaml](examples/metadata_example.yaml) for rule-based metadata (used with RuleEngine).

## LLM Providers

The `generate` command defaults to `gpt-4`. Set your API key in a `.env` file:

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Supported via [LiteLLM](https://docs.litellm.ai/): OpenAI, Anthropic, AWS Bedrock, Azure, and 100+ providers.

Use `--provider mock` for testing without an API key.

## Architecture

FHIR Synth is organized into focused packages:

- **`bundle/`** — Bundle creation and management (BundleBuilder, BundleManager, BundleFactory)
- **`code_generator/`** — LLM-powered code generation with self-healing execution
- **`rule_engine/`** — Declarative rule engine and EMPI logic
- **`fhir_utils/`** — FHIR resource factory utilities

See [ARCHITECTURE.md](ARCHITECTURE.md) for complete system design, data flows, and class diagrams.

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
```

Or manually:

```bash
pytest -q
mypy src
ruff check src
ruff format src
```

## License

MIT

