# FHIR Synth

Dynamic FHIR synthetic data generator using LLM-powered code generation and declarative rules (supports R4B, STU3).

Generate realistic synthetic healthcare data from natural language prompts. Tell it what you want, and it generates the code to create it.

> *Inspired by [Synthea](https://github.com/synthetichealth/synthea). Created and designed by human. Code guided by AI, for AI.*

## What It Does

```
Your Prompt
    ↓
Rules / Code Generation (LLM via LiteLLM)
    ↓
FHIR Resources (Patient, Condition, Observation, etc.)
    ↓
FHIR Bundles (JSON + NDJSON) — R4B or STU3
```

## Install

```bash
pip install git+https://github.com/alvinhenrick/fhir-synth.git
```

## Quick Start

### 1. Set up your LLM provider

```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

### 2. Generate data from a prompt

Describe what you need in plain English → get NDJSON output (one patient bundle per line):

```bash
# 10 diabetic patients with labs (uses gpt-4 by default)
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.ndjson

# 5 patients with hypertension, encounters, and meds
fhir-synth generate "5 patients with hypertension, office encounters, and antihypertensive medications" -o hypertension.ndjson

# Save the generated code for inspection
fhir-synth generate "20 patients with conditions and observations" -o data.ndjson --save-code generated.py

# Split output into one JSON file per patient
fhir-synth generate "10 diabetic patients" --split -o patients/

# Apply custom metadata (security labels, tags, profiles)
fhir-synth generate "10 patients" --meta-config examples/meta-normal.yaml -o output.ndjson

# EMPI: Person → Patients across EMR systems
fhir-synth generate "EMPI dataset" --empi --persons 3 -o empi.ndjson

# Stateful generation: add follow-up encounters to existing patients
fhir-synth generate "5 diabetic patients" -o initial.ndjson
fhir-synth generate "follow-up visits with HbA1c labs" --context initial.ndjson -o followup.ndjson

# AWS Bedrock provider with named profile
fhir-synth generate "5 patients" \
  --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --aws-profile my-profile --aws-region us-east-1 -o output.json

# Try without an API key (mock LLM for testing)
fhir-synth generate "5 patients" --provider mock -o test.json

# Generate STU3 resources instead of R4B (case-insensitive)
fhir-synth generate "10 patients with diabetes" --fhir-version stu3 -o output.ndjson
```

**What happens under the hood:**
1. **Skills selection**: Your prompt is matched against 13+ built-in skills (patient demographics, medications, labs, etc.) using fuzzy keyword matching with typo tolerance
2. Your prompt + selected skills go to the LLM (via [LiteLLM](https://docs.litellm.ai/) — 100+ providers)
3. LLM generates Python code using `fhir.resources` (Pydantic FHIR models)
4. Code is safety-checked (import whitelist + dangerous builtins scan) and auto-fixed (naive datetimes → UTC)
5. Code executes via a pluggable executor backend (local subprocess, dify-sandbox, or E2B cloud)
6. **Enhanced FHIR validation** — offline validation using `fhir.resources`:
   - Strict Pydantic mode (comprehensive type/format checking)
   - Required field verification (e.g., `Observation.status`, `Observation.code`)
   - Cardinality validation (min/max array occurrences)
   - Reference integrity checks (cross-resource references)
7. If anything fails, the error is sent back to the LLM for self-healing (up to 2 retries)
8. Resources are split by patient and saved as FHIR Bundle (JSON) or NDJSON (R4B or STU3 depending on `--fhir-version`)

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
| `-e / --executor` | `local` | Execution backend: `local`, `dify`, or `e2b` |
| `--dify-url` | — | Base URL for dify-sandbox (or set `DIFY_SANDBOX_URL` env var) |
| `--skills-dir` | — | Directory with user-provided SKILL.md skills |
| `--selector` | `keyword` | Skill selection: `keyword` (fuzzy) or `faiss` (semantic) |
| `--score-threshold` | `0.3` | Min similarity score 0.0-1.0 (FAISS only) |
| `--context` | — | Path to NDJSON/JSON with existing resources for stateful generation |

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
from fhir_synth.code_generator import CodeGenerator, get_executor
from fhir_synth.bundle import (
    BundleBuilder, BundleManager, BundleFactory,
    split_resources_by_patient, write_ndjson, write_split_bundles,
)
from fhir_synth.fhir_utils import FHIRResourceFactory

# --- Generate code from prompts (default: local subprocess executor) ---
llm = get_provider("mock")
code_gen = CodeGenerator(llm)
code = code_gen.generate_code_from_prompt("Create 20 patients")
resources = code_gen.execute_generated_code(code)

# --- Use a different executor backend ---
executor = get_executor("dify", dify_url="http://sandbox.internal:8194")
code_gen = CodeGenerator(llm, executor=executor)
resources = code_gen.execute_generated_code(code)

# --- Build a bundle ---
builder = BundleBuilder(bundle_type="transaction")
builder.add_resources(resources)
bundle = builder.build()

# --- Split by patient and write NDJSON ---
per_patient = split_resources_by_patient(resources)
write_ndjson(per_patient, "all_patients.ndjson")

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

## Skills System

FHIR Synth uses a **skills system** to inject domain-specific knowledge into the LLM context. Skills are modular Markdown files that provide guidance on generating realistic FHIR data.

### Built-in Skills (13+)

The system includes 13+ built-in skills following the [agentskills.io](https://agentskills.io/specification) spec:

- **patient-variation** — Demographics, age distribution, race, ethnicity, language
- **medications** — RxNorm codes, dosing, timing, adherence patterns
- **vitals-and-labs** — LOINC codes, normal ranges, temporal patterns
- **comorbidity** — Disease clustering, chronic conditions
- **encounters** — Visit types, coding systems, class progression
- **coverage** — Insurance diversity (Medicare, Medicaid, commercial)
- **allergies-immunizations** — CVX codes, contraindications
- **careplan-goals** — Care coordination, goal tracking
- **diagnostics-documents** — Imaging, reports, procedures
- **sdoh** — Social determinants of health
- **edge-cases** — Missing data, ambiguous records
- **provenance-data-quality** — Audit trails, data quality flags
- **family-history** — Genetic conditions, family relationships

### Skill Selection

**Keyword selector** (default) — Zero-dependency fuzzy matching with typo tolerance:
```bash
# "diabtes" → "diabetes" ✓, "medicaton" → "medication" ✓
fhir-synth generate "10 diabtes patients with medicaton" -o output.ndjson
```

**FAISS selector** (optional) — Semantic similarity for advanced users:
```bash
# Install semantic dependencies
pip install fhir-synth[semantic]

# Use semantic matching
fhir-synth generate "5 patients" --selector faiss
```

### Custom Skills

Create your own skills in a directory with `SKILL.md` files:

```yaml
---
name: my-custom-skill
description: Generate oncology data with TNM staging
keywords: [cancer, oncology, staging, tnm, tumor]
resource_types: [Condition, Observation]
always: false
---

# Oncology Staging

Generate cancer conditions with TNM staging observations:
- Use SNOMED CT for primary cancer codes
- Include T (tumor), N (node), M (metastasis) observations
- Use LOINC 21908-9 for TNM staging panel
...
```

Use with:
```bash
fhir-synth generate "5 lung cancer patients" --skills-dir ~/.fhir-synth/skills
```

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

- **`skills/`** — Skill discovery and selection following agentskills.io spec (`SkillLoader`, `KeywordSelector`, `FaissSelector`)
- **`bundle/`** — Bundle creation and management (`BundleBuilder`, `BundleManager`, `BundleFactory`, `split_resources_by_patient`, `write_ndjson`, `write_split_bundles`)
- **`code_generator/`** — LLM-powered code generation with self-healing execution (`CodeGenerator`)
    - **`code_generator/executor/`** — Pluggable executor backends (`LocalSubprocessExecutor`, `DifySandboxExecutor`, `E2BExecutor`)
    - **`code_generator/fhir_validation.py`** — Enhanced offline FHIR validation (strict mode, required fields, cardinality, references)
- **`fhir_utils/`** — FHIR resource factory and lazy resource class map (`FHIRResourceFactory`)
- **`llm.py`** — Unified LLM provider interface via LiteLLM (`LLMProvider`, `get_provider`)
- **`cli.py`** — Typer-based CLI

### Executor Backends

| Backend | `--executor` | Install | Isolation |
|---------|-------------|---------|-----------|
| Local subprocess | `local` (default) | Built-in | Import whitelist + process isolation |
| Dify Sandbox | `dify` | `pip install "fhir-synth[dify]"` | seccomp + namespace isolation |
| E2B Cloud | `e2b` | `pip install "fhir-synth[e2b]"` | Fully isolated micro-VM |

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

