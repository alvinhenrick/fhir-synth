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
pip install fhir-synth[llm]
```

## Quick Start

### Generate Data from a Prompt (main command)

Describe what you need in plain English → get a valid FHIR R4B Bundle:

```bash
# 10 diabetic patients with labs
fhir-synth generate "10 diabetic patients with HbA1c observations" -o diabetes.json

# 5 patients with hypertension, encounters, and meds
fhir-synth generate "5 patients with hypertension, office encounters, and antihypertensive medications" \
  --provider gpt-4 -o hypertension.json

# Save the generated code for inspection
fhir-synth generate "20 patients with conditions and observations" -o data.json --save-code generated.py

# EMPI: Person → Patients across EMR systems
fhir-synth generate "EMPI dataset" --empi --persons 3 -o empi.json
```

What happens under the hood:
1. Your prompt goes to the LLM
2. LLM generates Python code using `fhir.resources` (Pydantic FHIR models)
3. Code is executed in a sandbox
4. If it fails, the error is sent back to the LLM for self-healing (up to 2 retries)
5. Resources are wrapped in a FHIR Bundle and saved

### Other Commands

#### Rules from Prompt

```bash
fhir-synth rules "100 diabetic patients with HbA1c monitoring" --out rules.json
```

#### Code from Prompt (without bundling)

```bash
fhir-synth codegen "Create 50 realistic patients" --out code.py
fhir-synth codegen "Create 50 realistic patients" --out code.py --execute
```

#### Bundle from NDJSON

```bash
fhir-synth bundle --resources data.ndjson --out bundle.json --type transaction
```

#### EMPI (Person → Patients)

```bash
fhir-synth bundle --empi --out empi_bundle.json
fhir-synth bundle --empi --persons 5 --systems emr1,emr2,emr3 --no-orgs --out empi_bundle.json
```

## CLI Commands

### `fhir-synth generate` (primary)
End-to-end: prompt → LLM → code → execute → FHIR Bundle.

```bash
fhir-synth generate "10 diabetic patients with HbA1c labs" -o diabetes.json
fhir-synth generate "5 ER encounters with vitals" --provider gpt-4 -o er.json --save-code er.py
```

### `fhir-synth rules`
Generate structured rule definitions from natural language.

```bash
fhir-synth rules "100 diabetic patients with insulin therapy" \
  --out rules.json \
  --provider gpt-4
```

### `fhir-synth codegen`
Generate executable Python code from prompts (without bundling).

```bash
fhir-synth codegen "Create 50 patients" --out code.py
fhir-synth codegen "Create 50 patients" --out code.py --execute
```

### `fhir-synth bundle`
Create FHIR R4B bundles from NDJSON data or EMPI defaults.

```bash
fhir-synth bundle --resources data.ndjson --out bundle.json --type transaction
fhir-synth bundle --empi --out empi_bundle.json
```

**EMPI options (rules/codegen/bundle):**
- `--empi` include EMPI Person → Patient linkage
- `--persons` number of Persons (default: 1)
- `--systems` comma-separated EMR systems (default: emr1,emr2)
- `--no-orgs` skip Organization resources

## Python API

```python
from fhir_synth.llm import get_provider
from fhir_synth.code_generator import CodeGenerator
from fhir_synth.rule_engine import RuleEngine, Rule, RuleSet
from fhir_synth.bundle_builder import BundleBuilder
from fhir_synth.fhir_utils import FHIRResourceFactory

llm = get_provider("mock")
code_gen = CodeGenerator(llm)
code = code_gen.generate_code_from_prompt("Create 20 patients")
resources = code_gen.execute_generated_code(code)

engine = RuleEngine()
engine.register_ruleset(
    RuleSet(
        resource_type="Patient",
        description="Diabetic patients",
        rules=[
            Rule(
                name="type_2",
                description="Type 2 diabetes",
                conditions={"type": 2},
                actions={"resourceType": "Patient", "id": "p1"},
                weight=1.0,
            )
        ],
    )
)

patient = FHIRResourceFactory.create_patient("p1", "Jane", "Doe", "1990-01-01")
```

## LLM Providers

Create a `.env` file with your API key:

```bash
echo "OPENAI_API_KEY=sk-..." > .env
```

Supported providers: OpenAI, Anthropic, AWS Bedrock, and 100+ via LiteLLM. Default is `mock`.

## Architecture

See `ARCHITECTURE.md` for system design and data flows.

## Development

```bash
pytest -q
mypy src
ruff check src
ruff format src
```

## License

MIT

