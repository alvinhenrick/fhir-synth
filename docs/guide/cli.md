# CLI Reference

## `fhir-synth generate`

End-to-end: prompt → LLM → code → execute → NDJSON.

```bash
fhir-synth generate "10 diabetic patients with HbA1c observations"
```

### Output Structure

All outputs are saved to `runs/` with an auto-generated Docker-style name (e.g. `brave_phoenix`).
Each run creates its own directory:

```
runs/brave_phoenix/
  prompt.txt              ← the user's prompt
  brave_phoenix.py        ← generated Python code
  brave_phoenix.ndjson    ← NDJSON data (one patient bundle per line)
  patient_001.json        ← (with --split) per-patient JSON files
  patient_002.json
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-p` / `--provider` | `gpt-4` | LLM model/provider |
| `--fhir-version` | `R4B` | FHIR version: `R4B`, `STU3` (case-insensitive) |
| `--split` | off | Also write per-patient JSON files into the run directory |
| `--empi` | off | Include EMPI Person→Patient linkage |
| `--persons` | `1` | Number of Persons (EMPI) |
| `--systems` | `emr1,emr2` | Comma-separated EMR system ids (EMPI) |
| `--no-orgs` | off | Skip Organization resources (EMPI) |
| `--meta-config` | — | Path to metadata YAML config file |
| `-e` / `--executor` | `local` | Execution backend: `local`, `docker`, `e2b`, or `blaxel` |
| `--aws-profile` | — | AWS profile for Bedrock |
| `--aws-region` | — | AWS region for Bedrock |
| `--skills-dir` | — | Directory with user-provided `SKILL.md` skills |
| `--selector` | `keyword` | Skill selection: `keyword` (fuzzy) or `faiss` (semantic) |
| `--score-threshold` | `0.3` | Minimum similarity score 0.0–1.0 (FAISS only) |
| `--context` | — | Path to NDJSON/JSON with existing resources for stateful generation |

All executor backends are powered by [smolagents](https://huggingface.co/docs/smolagents).

### Examples

```bash
# Basic usage — output in runs/brave_phoenix/
fhir-synth generate "10 diabetic patients with HbA1c observations"

# Split into per-patient JSON files alongside the NDJSON
fhir-synth generate "10 diabetic patients with HbA1c observations" --split

# EMPI: Person → Patient linkages across EMR systems
fhir-synth generate "EMPI dataset" --empi --persons 3

# Apply metadata (security labels, tags, profiles) from YAML
fhir-synth generate "20 patients" --meta-config examples/meta-normal.yaml

# Mock provider — no API key needed, great for testing
fhir-synth generate "5 patients" --provider mock

# Sandboxed execution backends
fhir-synth generate "5 patients" --executor docker   # Docker container
fhir-synth generate "5 patients" --executor e2b      # E2B cloud sandbox
fhir-synth generate "5 patients" --executor blaxel   # Blaxel cloud sandbox

# Generate STU3 resources instead of R4B
fhir-synth generate "10 patients with diabetes" --fhir-version stu3

# Stateful generation: add follow-ups to existing patients
fhir-synth generate "follow-up visits with HbA1c labs" \
  --context runs/brave_phoenix/brave_phoenix.ndjson

# Custom skills directory
fhir-synth generate "5 lung cancer patients" --skills-dir ~/.fhir-synth/skills

# FAISS semantic skill selection (requires: pip install fhir-synth[semantic])
fhir-synth generate "5 patients" --selector faiss --score-threshold 0.5

# AWS Bedrock provider
fhir-synth generate "5 patients" \
  --provider bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0 \
  --aws-profile my-profile --aws-region us-east-1
```

### Environment Variables

| Variable | Used by | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `--provider gpt-4` | OpenAI API key |
| `ANTHROPIC_API_KEY` | `--provider claude-*` | Anthropic API key |
| `E2B_API_KEY` | `--executor e2b` | API key for [E2B](https://e2b.dev) cloud sandbox |

---

## `fhir-synth codegen`

Generate executable Python code from a prompt (without bundling or NDJSON output).

```bash
# Generate code only
fhir-synth codegen "Create 50 patients" --out code.py

# Generate and execute
fhir-synth codegen "Create 50 patients" --out code.py --execute

# Execute with Docker isolation
fhir-synth codegen "Create 50 patients" --out code.py --execute --executor docker
```

---

## `fhir-synth bundle`

Create a FHIR Bundle from existing NDJSON resources.

```bash
fhir-synth bundle --resources data.ndjson --out bundle.json --type transaction
```
