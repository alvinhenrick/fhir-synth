# FHIR Synth - Quick Start Guide

## 🚀 Get Started in 5 Minutes

FHIR Synth is an **alpha-stage FHIR synthetic data generator** that creates realistic, reproducible healthcare data for testing and development.

## Prerequisites

- Python 3.11+
- pip or uv package manager

## Installation

```bash
# Install the project
pip install -e ".[dev]"

# Or with uv
uv sync

# Optional: Setup API keys for LLM features
cp .env.example .env
# Edit .env and add your OpenAI/Anthropic/AWS keys (optional)
```

## Quick Examples

### 1️⃣ Generate Simple Datasets (No Setup Needed!)

```bash
# Create example configs
fhir-synth init

# Generate 10 patients for 1 year
fhir-synth generate -c examples/minimal.yml -o ./output

# Check the output
cat output/output.ndjson | head -5
```

### 2️⃣ Multi-Organization (EMPI) Testing

```bash
# Perfect for master patient index and record linkage testing
fhir-synth generate -c examples/multi-org.yml -o ./empi_test
```

Expected output:
- 1 Person entity per real patient
- 2-3 Patient records per person (across different hospitals)
- Realistic clinical data linked to each Patient
- Great for testing EMPI resolution algorithms

### 3️⃣ Generate Config from Natural Language (Optional - needs API key)

```bash
# Setup (one time)
cp .env.example .env
# Edit .env and add OPENAI_API_KEY=sk-...

# Use natural language to create config
fhir-synth prompt "100 diabetic patients from 2 hospitals" --out my_config.yml

# Generate data from that config
fhir-synth generate -c my_config.yml -o ./output
```

Or use the built-in mock LLM (no API key needed):
```bash
fhir-synth prompt "50 patients with various conditions" --out config.yml  # Uses mock by default
fhir-synth generate -c config.yml -o ./output
```

### 4️⃣ Use as Python Library

```python
from fhir_synth.plan import DatasetPlan
from fhir_synth.generator import DatasetGenerator

# Load config
plan = DatasetPlan.from_yaml("config.yml")

# Generate data
generator = DatasetGenerator(plan)
graph = generator.generate()

# Use the resources
for patient in graph.get_all("Patient"):
    print(f"Patient: {patient.id}")
```

## What Gets Generated?

Each run creates FHIR R4 compliant resources:

| Resource | Quantity | Purpose |
|----------|----------|---------|
| Person | 1 per person | Identity anchor |
| Patient | 1-3 per person | Source system records |
| Organization | 1-2 | Healthcare provider(s) |
| Practitioner | 2-5 | Doctors/nurses |
| Location | 2-5 | Clinics/hospitals |
| Encounter | 2-8 per patient | Visits/admissions |
| Observation | 5-15 per patient | Lab/vital results |
| Condition | 1-3 per patient | Diagnoses |
| MedicationRequest | 1-4 per patient | Prescriptions |
| Procedure | 0-2 per patient | Surgeries |
| AllergyIntolerance | 0-2 per patient | Allergies |

## Common Commands

### View Help
```bash
fhir-synth --help
fhir-synth generate --help
```

### Create Templates
```bash
fhir-synth init                    # All examples
fhir-synth init --minimal          # Just minimal
fhir-synth init --multi-org        # Just multi-org
```

### Generate Data
```bash
# From minimal config (10 patients, 1 year)
fhir-synth generate -c examples/minimal.yml -o ./output

# Override seed for reproducibility
fhir-synth generate -c config.yml -o ./data --seed 42

# Regenerate exact same data
fhir-synth generate -c config.yml -o ./data --seed 42  # Same output!
```

### Check Output
```bash
# View first record
head -1 output/output.ndjson | python -m json.tool

# Count records
wc -l output/output.ndjson

# Get summary
grep -o '"resourceType":"[^"]*"' output/output.ndjson | sort | uniq -c
```

## Development

### Run Quality Checks
```bash
# Check code quality (linting + type checking)
hatch run check

# Auto-format code
hatch run format

# Auto-fix issues
hatch run lint
```

### Run Tests
```bash
# All tests
hatch run test

# With coverage
hatch run cov

# Specific test file
pytest tests/test_generator.py -v
```

## Configuration

### Minimal Config (10 patients, 1 year)
```yaml
version: 1
seed: 42
population:
  persons: 10
time:
  horizon: {years: 1}
outputs:
  format: ndjson
  path: ./output
```

### Multi-Org Config (EMPI Testing)
```yaml
version: 1
seed: 42
population:
  persons: 50
  sources:
    - id: hospital1
      organization: {name: "Hospital A"}
      patient_id_namespace: "hospital1"
      weight: 0.5
    - id: hospital2
      organization: {name: "Hospital B"}
      patient_id_namespace: "hospital2"
      weight: 0.5
  person_appearance:
    systems_per_person_distribution:
      1: 0.70   # 70% in one hospital
      2: 0.25   # 25% in both hospitals
      3: 0.05   # 5% in three
time:
  horizon: {years: 3}
outputs:
  format: ndjson
  path: ./output
```

## Environment Variables (Optional)

If you want to use real LLM providers for the `prompt` command:

```bash
# Create .env file
cp .env.example .env

# Add your API keys
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# AWS_ACCESS_KEY_ID=...
```

Then use:
```bash
fhir-synth prompt "your description" --out config.yml --provider gpt-4
```

**Without .env:** Uses built-in mock LLM (works fine for testing)

## FAQ

**Q: Do I need an API key?**
A: No! The mock LLM provider works without keys. Real LLM features are optional.

**Q: How do I regenerate exact same data?**
A: Use the same seed: `fhir-synth generate -c config.yml --seed 42`

**Q: Can I use this in production?**
A: It's Alpha stage. Great for testing/development. Check the status in README.md.

**Q: What FHIR servers does this work with?**
A: Any FHIR R4 server that accepts NDJSON bulk import.

**Q: How do I load data into my FHIR server?**
A: Most FHIR servers support bulk import. Check your server's documentation.

**Q: Can I customize the data?**
A: Yes! Edit the YAML config or use `fhir-synth prompt` with your description.

## Next Steps

1. **Run the examples:**
   ```bash
   fhir-synth init
   fhir-synth generate -c examples/minimal.yml -o ./output
   ```

2. **Read the full docs:**
   ```bash
   cat README.md
   ```

3. **View generated data:**
   ```bash
   cat output/output.ndjson | python -m json.tool | head -50
   ```

4. **Create your own config:**
   - Edit one of the example YAMLs
   - Or use: `fhir-synth prompt "your description" --out config.yml`
   - Then: `fhir-synth generate -c config.yml -o ./output`

## Troubleshooting

**"command not found: fhir-synth"**
- Make sure you're in the project directory
- Run: `pip install -e .`

**"API key not found"**
- This is normal - you're using the mock provider
- To use real APIs: Copy `.env.example` to `.env` and add your keys

**"No module named fhir_synth"**
- Install dependencies: `pip install -e ".[dev]"`

**Need more help?**
- Check `README.md` for full documentation
- Run `fhir-synth --help` for CLI help
- Check the test files for usage examples

---

**Ready?** Run `fhir-synth init` to get started! 🚀

