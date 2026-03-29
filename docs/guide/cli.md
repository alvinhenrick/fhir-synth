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
| `--fhir-version` | `R4B` | FHIR version: `R4B`, `STU3` (case-insensitive) |
| `--split` | off | Split output: one JSON file per patient in a directory |
| `--save-code` | — | Save generated Python code |
| `--empi` | off | Include EMPI Person→Patient linkage |
| `--persons` | `1` | Number of Persons (EMPI) |
| `--systems` | `emr1,emr2` | EMR system ids (EMPI) |
| `--no-orgs` | off | Skip Organization resources (EMPI) |
| `--meta-config` | — | Path to metadata YAML config file |
| `-e / --executor` | `local` | Execution backend: `local`, `docker`, `e2b`, or `blaxel` (powered by [smolagents](https://huggingface.co/docs/smolagents)) |
| `--docker-host` | — | Docker host for docker executor (default: `127.0.0.1`) |
| `--docker-port` | — | Docker port for docker executor (default: `8888`) |
| `--blaxel-sandbox` | — | Sandbox name for Blaxel executor |
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

# Docker sandbox executor — runs code in an isolated Docker container
fhir-synth generate "5 patients" --executor docker

# Docker sandbox with explicit host/port
fhir-synth generate "5 patients" --executor docker --docker-host 192.168.1.1 --docker-port 9999

# E2B cloud sandbox (requires E2B_API_KEY env var)
fhir-synth generate "5 patients" --executor e2b

# Blaxel cloud sandbox
fhir-synth generate "5 patients" --executor blaxel

# Generate STU3 resources instead of R4B (case-insensitive)
fhir-synth generate "10 patients with diabetes" --fhir-version stu3 -o output.ndjson
fhir-synth generate "5 patients" --fhir-version STU3 -o output.ndjson
```

### Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `E2B_API_KEY` | `--executor e2b` | API key for [E2B](https://e2b.dev) cloud sandbox |

---

## `fhir-synth codegen`

Generate executable Python code from prompts (without bundling).

```bash
fhir-synth codegen "Create 50 patients" --out code.py
fhir-synth codegen "Create 50 patients" --out code.py --execute

# Execute with Docker isolation
fhir-synth codegen "Create 50 patients" --out code.py --execute --executor docker
```

---

## `fhir-synth bundle`

Create FHIR Bundles from NDJSON data or EMPI defaults.

```bash
fhir-synth bundle --resources data.ndjson --out bundle.json --type transaction
fhir-synth bundle --empi --persons 5 --systems emr1,emr2,emr3 --no-orgs --out empi_bundle.json
```

