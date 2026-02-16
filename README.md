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

### 1) Rules from Prompt

```bash
fhir-synth rules "100 diabetic patients with HbA1c monitoring" --out rules.json
```

### 2) Code from Prompt

```bash
fhir-synth codegen "Create 50 realistic patients" --out code.py
fhir-synth codegen "Create 50 realistic patients" --out code.py --execute
```

### 3) Bundle from NDJSON

```bash
fhir-synth bundle --resources data.ndjson --out bundle.json --type transaction
```

### 4) EMPI (Person → Patients)

```bash
# Rules with EMPI metadata
fhir-synth rules "EMPI dataset" --empi --out rules.json

# Codegen with EMPI linkage
fhir-synth codegen "EMPI dataset" --empi --out code.py --execute

# Bundle with EMPI resources (1 person, emr1+emr2)
fhir-synth bundle --empi --out empi_bundle.json

# Custom EMPI parameters
fhir-synth bundle --empi --persons 5 --systems emr1,emr2,emr3 --no-orgs --out empi_bundle.json
```

## CLI Commands

### `fhir-synth rules`
Generate structured rule definitions from natural language.

```bash
fhir-synth rules "100 diabetic patients with insulin therapy" \
  --out rules.json \
  --provider gpt-4
```

### `fhir-synth codegen`
Generate executable Python code from prompts.

```bash
fhir-synth codegen "Create 50 patients" --out code.py
fhir-synth codegen "Create 50 patients" --out code.py --execute
```

### `fhir-synth bundle`
Create FHIR R4B bundles from NDJSON data or EMPI defaults.

```bash
# NDJSON bundle
fhir-synth bundle --resources data.ndjson --out bundle.json --type transaction

# EMPI bundle (Person → Patients)
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

