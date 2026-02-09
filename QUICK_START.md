# FHIR Synth - Quick Start Guide

## 🚀 Get Started in 5 Minutes

FHIR Synth is a **production-ready FHIR synthetic data generator** that creates realistic healthcare data for testing and development.

## What You Can Do

### 1️⃣ **Generate Simple Datasets**
```bash
# Create example configs
fhir-synth init

# Generate 10 patients for 1 year
fhir-synth generate -c examples/minimal.yml -o ./output
```

No code needed. Just one command to get realistic FHIR data.

### 2️⃣ **Multi-Organization (EMPI) Testing**
```bash
# Perfect for master patient index and record linkage testing
fhir-synth generate -c examples/multi-org.yml -o ./empi_test
```

Expected output:
- 1 Person = 2-3 Patients across different source systems
- Realistic clinical data per source
- Perfect for testing EMPI resolution

### 3️⃣ **Generate from Natural Language**
```bash
# No YAML needed - just describe what you want
fhir-synth prompt "100 diabetic patients from 2 hospitals" --out config.yml
fhir-synth generate -c config.yml -o ./output
```

### 4️⃣ **Bulk Load Testing**
```bash
# Generate 500+ patients for performance testing
fhir-synth generate --config bulk_config.yml --seed 42 --output ./bulk_data
```

### 5️⃣ **Use as Python Library**
```python
from fhir_synth.plan import DatasetPlan
from fhir_synth.generator import DatasetGenerator

plan = DatasetPlan.from_yaml("config.yml")
generator = DatasetGenerator(plan)
generator.generate()
```

## What's in the Output?

Each generation creates FHIR R4 compliant resources ready for your system:

| Resource | Count | Purpose |
|----------|-------|---------|
| Person | 1 per person | Identity anchor |
| Patient | 1-3 per person | Source system records |
| Organization | 1 per source | Healthcare provider |
| Practitioner | Variable | Doctors/nurses |
| Location | Variable | Clinics/hospitals |
| Encounter | 5-10 per patient | Visits/admissions |
| Condition | 1-3 per patient | Diagnoses |
| Observation | 5-15 per patient | Lab/vital results |
| MedicationRequest | 1-4 per patient | Prescriptions |
| MedicationDispense | 60% of requests | Fulfillments |
| Procedure | 0-2 per patient | Surgeries |
| AllergyIntolerance | 0-2 per patient | Drug/food allergies |
| CarePlan | Variable | Treatment plans |
| DocumentReference | 1-3 per patient | Clinical documents |

## Why Use FHIR Synth?

✅ **Deterministic** - Reproduce the same data (great for testing)
✅ **Reference Integrity** - All relationships are valid
✅ **Realistic Timelines** - Clinical events happen in correct order
✅ **Multi-org Support** - Test EMPI and record linking
✅ **LLM-assisted** - Describe what you want, system generates config
✅ **Ready to Use** - Output works with FHIR servers immediately

## Commands

### Create Example Configs
```bash
fhir-synth init [--minimal|--full|--multi-org] [--output DIR]
```
Creates sample YAML config files to get you started.

### Generate from Description
```bash
fhir-synth prompt "100 diabetic patients from 2 hospitals" --out config.yml
fhir-synth generate -c config.yml -o ./output
```
No need to write YAML - just describe what you want!

### Generate from Config
```bash
fhir-synth generate --config FILE [--output DIR] [--seed N]
```
Load your YAML config and generate FHIR data.

### Validate Your Data
```bash
fhir-synth validate --input DIR
```
Check that generated data meets FHIR standards.

## Configuration Examples

Want to customize? Here are some examples:

### Simple: 10 Patients, 1 Year
```yaml
version: 1
seed: 42
population:
  persons: 10
time:
  horizon: {years: 1}
```

### EMPI: Multiple Hospital Systems
```yaml
version: 1
seed: 42
population:
  persons: 50
  sources:
    - id: hospital1
      organization: {name: "Hospital A"}
      patient_id_namespace: "hospital1"
    - id: hospital2
      organization: {name: "Hospital B"}
      patient_id_namespace: "hospital2"
  person_appearance:
    systems_per_person_distribution:
      1: 0.70   # 70% in one hospital
      2: 0.25   # 25% in both hospitals
      3: 0.05   # 5% in all three
time:
  horizon: {years: 3}
```

## Installation

```bash
# Basic installation
pip install fhir-synth

# With LLM support (OpenAI, Anthropic, Bedrock)
pip install fhir-synth[llm]

# Development
pip install -e ".[dev]"
```

## Getting Started (3 Steps)

### Step 1: Install
```bash
pip install fhir-synth
```

### Step 2: Generate Data
```bash
# Option A: Simple CLI
fhir-synth init
fhir-synth generate -c examples/minimal.yml -o ./output

# Option B: Describe what you want
fhir-synth prompt "50 patients with diabetes" --out config.yml
fhir-synth generate -c config.yml -o ./output
```

### Step 3: Use the Data
Your data is in `./output/output.ndjson` - ready to:
- Load into a FHIR server
- Use in your test suite
- Analyze with your tools
- Feed into your pipeline

## Need Help?

- **Full Documentation**: See `README.md`
- **Example Configs**: Run `fhir-synth init`
- **CLI Help**: Run `fhir-synth --help`
- **View Generated Data**: Check `output/output.ndjson`

## Common Questions

**Q: Can I regenerate the exact same data?**
A: Yes! Use the same seed: `fhir-synth generate -c config.yml --seed 42`

**Q: How do I use this with my FHIR server?**
A: Load the NDJSON file directly: Most FHIR servers support bulk import from NDJSON.

**Q: Can I customize the data?**
A: Yes! Edit the YAML config or use `fhir-synth prompt` with your description.

**Q: What FHIR resources are included?**
A: Person, Patient, Organization, Practitioner, Encounter, Condition, Observation, Medication, Procedure, AllergyIntolerance, CarePlan, DocumentReference, and more.

---

**Ready to generate synthetic FHIR data?** Run `fhir-synth init` and pick an example to get started! 🚀

