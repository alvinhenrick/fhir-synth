# CLI Reference

## `fhir-synth generate`

End-to-end: prompt → LLM → code → execute → NDJSON.

```bash fhir-synth generate "10 diabetic patients with HbA1c observations"
```

All outputs are saved to a `runs/` directory with an auto-generated Docker-style name (e.g. `brave_phoenix`). Each run creates its own directory:

- `runs/<name>/prompt.txt`     — the user's prompt
- `runs/<name>/<name>.py`      — the generated Python code
- `runs/<name>/<name>.ndjson`  — NDJSON data (one patient bundle per line)
- `runs/<name>/patient_*.json` — (with `--split`) per-patient JSON files

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-p / --provider` | `gpt-4` | LLM model/provider |
| `--fhir-version` | `R4B` | FHIR version: `R4B`, `STU3` (case-insensitive) |
| `--split` | off | Also split output into one JSON file per patient in a subdirectory |
| `--empi` | off | Include EMPI Person→Patient linkage |
| `--persons` | `1` | Number of Persons (EMPI) |
| `--systems` | `emr1,emr2` | EMR system ids (EMPI) |
| `--no-orgs` | off | Skip Organization resources (EMPI) |
| `--meta-config` | — | Path to metadata YAML config file |
| `-e / --executor` | `local` | Execution backend: `local`, `docker`, `e2b`, or `blaxel` (powered by [smolagents](https://huggingface.co/docs/smolagents)) |
| `--aws-profile` | — | AWS profile for Bedrock |
| `--aws-region` | — | AWS region for Bedrock |
| `--skills-dir` | — | Directory with user-provided SKILL.md skills |
| `--selector` | `keyword` | Skill selection: `keyword` (fuzzy) or `faiss` (semantic) |
| `--score-threshold` | `0.3` | Min similarity score 0.0-1.0 (FAISS only) |
| `--context` | — | Path to NDJSON/JSON with existing resources for stateful generation |

### Examples

```bash
# Default: generates runs/brave_phoenix/ with prompt.txt, .py, .ndjson
fhir-synth generate "10 diabetic patients with HbA1c observations"

# Also split per patient → runs/<name>/patient_001.json ...
fhir-synth generate "10 diabetic patients with HbA1c observations" --split

# With EMPI
fhir-synth generate "EMPI dataset" --empi --persons 3

# With metadata from YAML
fhir-synth generate "20 patients" --meta-config examples/meta-normal.yaml

# Mock provider (no API key needed)
fhir-synth generate "5 patients" --provider mock

# Docker sandbox executor — runs code in an isolated Docker container
fhir-synth generate "5 patients" --executor docker

# E2B cloud sandbox (requires E2B_API_KEY env var)
fhir-synth generate "5 patients" --executor e2b

# Blaxel cloud sandbox
fhir-synth generate "5 patients" --executor blaxel

# Generate STU3 resources instead of R4B (case-insensitive)
fhir-synth generate "10 patients with diabetes" --fhir-version stu3
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

