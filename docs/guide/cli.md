# CLI Reference

## `fhir-synth generate`

End-to-end: prompt → LLM → code → execute → NDJSON.

```bash
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.ndjson
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o / --out` | `output.ndjson` | Output file (or directory with `--split`) |
| `-p / --provider` | `gpt-4` | LLM model/provider |
| `--split` | off | Split output: one JSON file per patient in a directory |
| `--save-code` | — | Save generated Python code |
| `--empi` | off | Include EMPI Person→Patient linkage |
| `--persons` | `1` | Number of Persons (EMPI) |
| `--systems` | `emr1,emr2` | EMR system ids (EMPI) |
| `--no-orgs` | off | Skip Organization resources (EMPI) |
| `--meta-config` | — | Path to metadata YAML config file |
| `-e / --executor` | `local` | Execution backend: `local`, `dify`, or `e2b` |
| `--dify-url` | — | Base URL for dify-sandbox (or set `DIFY_SANDBOX_URL` env var) |
| `--aws-profile` | — | AWS profile for Bedrock |
| `--aws-region` | — | AWS region for Bedrock |

Default output is a single NDJSON file (one patient bundle per line).
Use `--split` to write one JSON file per patient into a directory instead.

### Examples

```bash
# Default: single NDJSON file (one patient bundle per line)
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.ndjson

# Split per patient → patients/patient_001.json ...
fhir-synth generate "10 diabetic patients with HbA1c observations" --split -o patients/

# With EMPI
fhir-synth generate "EMPI dataset" --empi --persons 3 -o empi.ndjson

# With metadata from YAML
fhir-synth generate "20 patients" --meta-config examples/meta-normal.yaml -o output.ndjson

# Save generated code for inspection
fhir-synth generate "20 patients with conditions" -o data.ndjson --save-code generated.py

# Mock provider (no API key needed)
fhir-synth generate "5 patients" --provider mock -o test.ndjson

# Dify sandbox executor — sends code to a dify-sandbox service
fhir-synth generate "5 patients" --executor dify

# Dify sandbox with explicit URL
fhir-synth generate "5 patients" --executor dify --dify-url http://sandbox.internal:8194

# Dify enterprise/cloud (set DIFY_SANDBOX_API_KEY for auth)
# export DIFY_SANDBOX_URL=https://dify.yourcompany.com
# export DIFY_SANDBOX_API_KEY=your-key
fhir-synth generate "5 patients" --executor dify

# E2B cloud sandbox (requires E2B_API_KEY env var)
fhir-synth generate "5 patients" --executor e2b
```

### Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `DIFY_SANDBOX_URL` | `--executor dify` | Dify sandbox URL (default: `http://localhost:8194`) |
| `DIFY_SANDBOX_API_KEY` | `--executor dify` | API key for Dify enterprise/cloud (not needed for self-hosted) |
| `E2B_API_KEY` | `--executor e2b` | API key for [E2B](https://e2b.dev) cloud sandbox |

---

## `fhir-synth codegen`

Generate executable Python code from prompts (without bundling).

```bash
fhir-synth codegen "Create 50 patients" --out code.py
fhir-synth codegen "Create 50 patients" --out code.py --execute

# Execute with dify-sandbox isolation
fhir-synth codegen "Create 50 patients" --out code.py --execute --executor dify
```

---

## `fhir-synth bundle`

Create FHIR R4B Bundles from NDJSON data or EMPI defaults.

```bash
fhir-synth bundle --resources data.ndjson --out bundle.json --type transaction
fhir-synth bundle --empi --persons 5 --systems emr1,emr2,emr3 --no-orgs --out empi_bundle.json
```

