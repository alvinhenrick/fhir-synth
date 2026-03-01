# Quick Start

## Generate Data from a Prompt

Describe what you need in plain English — FHIR Synth generates the code and executes it:

```bash
# 10 diabetic patients with labs → single NDJSON file (one patient bundle per line)
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.ndjson

# Split: one JSON file per patient in a directory
fhir-synth generate "10 diabetic patients with HbA1c observations" --split -o patients/

# 5 patients with hypertension, encounters, and meds
fhir-synth generate "5 patients with hypertension, office encounters, and antihypertensive medications" -o hypertension.ndjson
```

## What Happens Under the Hood

1. Your prompt goes to the LLM (with FHIR spec, import guide, and sandbox constraints)
2. LLM generates Python code using `fhir.resources` (Pydantic FHIR models)
3. Code is safety-checked (import whitelist + dangerous builtins scan) and auto-fixed (naive datetimes → UTC)
4. Code executes in an isolated subprocess with a timeout
5. Output is smoke-tested (non-empty, every resource has `resourceType`)
6. If anything fails, the error is sent back to the LLM for self-healing (up to 2 retries)
7. Resources are grouped by patient and saved as NDJSON

## Save Generated Code

Inspect the code the LLM generates:

```bash
fhir-synth generate "20 patients with conditions" -o data.json --save-code generated.py
```

## EMPI Mode

Generate Person → Patient linkages across EMR systems:

```bash
fhir-synth generate "EMPI dataset" --empi --persons 3 -o empi.json
```

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
fhir-synth generate "20 patients" --meta-config examples/meta-normal.yaml -o output.json
```

## Test Without an API Key

```bash
fhir-synth generate "5 patients" --provider mock -o test.json
```

