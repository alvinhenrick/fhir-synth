# Quick Start

## Generate Data from a Prompt

Describe what you need in plain English — FHIR Synth generates the code and executes it.
All outputs are auto-saved to `runs/` with a unique Docker-style name (e.g. `brave_phoenix`):

```bash
# 10 diabetic patients with labs → runs/brave_phoenix/
fhir-synth generate "10 diabetic patients with HbA1c observations"

# Also split: one JSON file per patient in the run directory
fhir-synth generate "10 diabetic patients with HbA1c observations" --split

# 5 patients with hypertension, encounters, and meds
fhir-synth generate "5 patients with hypertension, office encounters, and antihypertensive medications"

# Generate STU3 resources instead of R4B (case-insensitive)
fhir-synth generate "10 patients with diabetes" --fhir-version stu3
```

## What Happens Under the Hood

1. **Skills selection**: Your prompt is matched against 16 built-in skills using fuzzy keyword matching with typo tolerance
2. Your prompt + selected skills go to the LLM (via [LiteLLM](https://docs.litellm.ai/) — 100+ providers)
3. LLM generates Python code using `fhir.resources` (Pydantic FHIR models)
4. Code is safety-checked (import whitelist + dangerous builtins scan) and auto-fixed (naive datetimes → UTC)
5. Code executes via a pluggable executor backend powered by [smolagents](https://huggingface.co/docs/smolagents) (local AST interpreter, Docker, E2B, or Blaxel)
6. **Enhanced FHIR validation** — offline validation using `fhir.resources`:
    - Pydantic model validation (required fields, types, cardinality)
    - Choice-type [x] mutual exclusion checks
    - Reference integrity checks (cross-resource references)
    - US Core compliance checks (must-support field coverage)
7. If anything fails, the error is sent back to the LLM for self-healing (up to 2 retries)
8. Resources are split by patient and saved as NDJSON

## Output Structure

Each run auto-generates a unique name and saves all artifacts in a directory:

```
runs/
  brave_phoenix/
    prompt.txt              ← the user's prompt
    brave_phoenix.py        ← generated Python code
    brave_phoenix.ndjson    ← NDJSON output (one patient bundle per line)
    patient_001.json        ← (with --split) per-patient JSON files
    patient_002.json
    ...
```

## EMPI Mode

Generate Person → Patient linkages across EMR systems:

```bash
fhir-synth generate "EMPI dataset" --empi --persons 3
```

## Two-Stage DSPy Pipeline

Use the optional DSPy pipeline for structured clinical planning before code generation:

```bash
# Two-stage: clinical planning → code synthesis
pip install 'fhir-synth[dspy]'
fhir-synth generate "5 diabetic patients with labs" --pipeline dspy

# Use a pre-optimized DSPy program (auto-selects dspy pipeline)
fhir-synth generate "5 diabetic patients" --compiled-program optimized.json
```

See [DSPy Pipeline](../guide/pipeline.md) for details.

## Use the Python API

```python
from fhir_synth.llm import get_provider
from fhir_synth.code_generator import CodeGenerator
from fhir_synth.bundle import BundleBuilder

# Generate code from prompts
llm = get_provider("mock")
code_gen = CodeGenerator(llm)
code = code_gen.generate_code_from_prompt("Create 20 patients")
resources = code_gen.execute_generated_code(code)

# Build a FHIR bundle
builder = BundleBuilder(bundle_type="transaction")
builder.add_resources(resources)
bundle = builder.build()
```

## Add Custom Metadata

Apply security labels, tags, and profiles via YAML:

```yaml
# meta-normal.yaml
meta:
  security:
    - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
      code: "R"
      display: "Restricted"
  tag:
    - system: "http://example.org/tags"
      code: "synthetic-data"
  source: "http://example.org/fhir-synth"
```

```bash
fhir-synth generate "20 patients" --meta-config examples/meta-normal.yaml
```

## Test Without an API Key

```bash
fhir-synth generate "5 patients" --provider mock
```

