# CLI Reference

## `fhir-synth generate`

End-to-end: prompt → LLM → code → execute → FHIR Bundle.

```bash
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.json
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o / --out` | `output.json` | Output file (or directory with `--split`) |
| `-p / --provider` | `gpt-4` | LLM model/provider |
| `-t / --type` | `transaction` | Bundle type |
| `--split` | off | Split output: one JSON file per patient |
| `--save-code` | — | Save generated Python code |
| `--empi` | off | Include EMPI Person→Patient linkage |
| `--persons` | `1` | Number of Persons (EMPI) |
| `--systems` | `emr1,emr2` | EMR system ids (EMPI) |
| `--no-orgs` | off | Skip Organization resources (EMPI) |
| `--meta-config` | — | Path to metadata YAML config file |
| `--aws-profile` | — | AWS profile name for Bedrock |
| `--aws-region` | — | AWS region for Bedrock (e.g. `us-east-1`) |

NDJSON output (one patient bundle per line) is always generated alongside the JSON output.

### Examples

```bash
# Single bundle (default) → output.json + output.ndjson
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.json

# Split per patient → patients/patient_001.json ... + patients/all_patients.ndjson
fhir-synth generate "10 diabetic patients with HbA1c observations" --split -o patients/

# With EMPI
fhir-synth generate "EMPI dataset" --empi --persons 3 -o empi.json

# With metadata from YAML
fhir-synth generate "20 patients" --meta-config examples/meta-normal.yaml -o output.json

# Save generated code for inspection
fhir-synth generate "20 patients with conditions" -o data.json --save-code generated.py

# Mock provider (no API key needed)
fhir-synth generate "5 patients" --provider mock -o test.json

# Anthropic Claude
fhir-synth generate "10 patients" --provider claude-3-5-sonnet-20241022 -o output.json

# AWS Bedrock with named profile
fhir-synth generate "10 patients" \
  --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --aws-profile my-profile --aws-region us-east-1 -o output.json

# Google Gemini
fhir-synth generate "10 patients" --provider gemini/gemini-pro -o output.json
```

---

## `fhir-synth rules`

Generate structured rule definitions from natural language.

```bash
fhir-synth rules "100 diabetic patients with insulin therapy" --out rules.json --provider gpt-4
```

---

## `fhir-synth codegen`

Generate executable Python code from prompts (without bundling).

```bash
fhir-synth codegen "Create 50 patients" --out code.py
fhir-synth codegen "Create 50 patients" --out code.py --execute
```

---

## `fhir-synth bundle`

Create FHIR R4B Bundles from NDJSON data or EMPI defaults.

```bash
fhir-synth bundle --resources data.ndjson --out bundle.json --type transaction
fhir-synth bundle --empi --persons 5 --systems emr1,emr2,emr3 --no-orgs --out empi_bundle.json
```

