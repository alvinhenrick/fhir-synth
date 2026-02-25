# CLI Reference

## `fhir-synth generate`

End-to-end: prompt → LLM → code → execute → FHIR Bundle.

```bash
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.json
```

### Options

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
| `--meta-config` | — | Path to metadata YAML config file |
| `--security` | — | Add security label (`system\|code\|display`) |
| `--tag` | — | Add tag (`system\|code\|display`) |
| `--profile` | — | Add profile URL |
| `--source` | — | Add source system URI |

### Examples

```bash
# Basic generation
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.json

# With EMPI
fhir-synth generate "EMPI dataset" --empi --persons 3 -o empi.json

# With metadata from YAML
fhir-synth generate "20 patients" --meta-config metadata.yaml -o output.json

# With inline metadata flags
fhir-synth generate "10 patients" \
  --security "http://terminology.hl7.org/CodeSystem/v3-Confidentiality|R|Restricted" \
  --tag "http://example.org/tags|synthetic|Synthetic Data" \
  --source "http://example.org/fhir-synth" \
  -o tagged.json

# Save generated code for inspection
fhir-synth generate "20 patients with conditions" -o data.json --save-code generated.py

# Mock provider (no API key needed)
fhir-synth generate "5 patients" --provider mock -o test.json
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

