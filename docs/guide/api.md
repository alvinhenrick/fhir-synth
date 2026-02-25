# Python API

Use FHIR Synth as a library in your Python code.

## Code Generation

```python
from fhir_synth.llm import get_provider
from fhir_synth.code_generator import CodeGenerator

# Set up LLM provider
llm = get_provider("gpt-4")  # or "mock" for testing

# Generate and execute code
code_gen = CodeGenerator(llm)
code = code_gen.generate_code_from_prompt("Create 20 diabetic patients with HbA1c observations")
resources = code_gen.execute_generated_code(code)
```

## Rule Engine

```python
from fhir_synth.rule_engine import RuleEngine, Rule, RuleSet, MetaConfig

engine = RuleEngine()
engine.register_ruleset(
    RuleSet(
        resource_type="Patient",
        description="Diabetic patients",
        global_meta=MetaConfig(
            tag=[{"system": "http://example.org/tags", "code": "synthetic"}],
            source="http://example.org/fhir-synth",
        ),
        rules=[
            Rule(
                name="type_2",
                description="Type 2 diabetes",
                conditions={"type": 2},
                actions={"resourceType": "Patient", "id": "p1"},
                weight=1.0,
                meta=MetaConfig(
                    security=[{
                        "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                        "code": "N",
                        "display": "Normal",
                    }],
                    profile=["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"],
                ),
            )
        ],
    )
)
```

## Bundle Building

```python
from fhir_synth.bundle import BundleBuilder, BundleManager

# Build a single bundle from resources
builder = BundleBuilder(bundle_type="transaction")
builder.add_resources(resources)
bundle = builder.build()

# Save to file
BundleManager.save(bundle, "output.json")
```

## Split Per Patient & NDJSON

```python
from pathlib import Path
from fhir_synth.bundle import split_resources_by_patient, write_split_bundles, write_ndjson

# Split resources into one bundle per patient
per_patient = split_resources_by_patient(resources)

# Write one JSON file per patient
write_split_bundles(per_patient, Path("patients/"))
# → patients/patient_001.json, patients/patient_002.json, ...

# Write NDJSON (one bundle per line)
write_ndjson(per_patient, Path("patients.ndjson"))
```

## FHIR Resource Factory

```python
from fhir_synth.fhir_utils import FHIRResourceFactory

# Create resources directly
patient = FHIRResourceFactory.create_patient("p1", "Jane", "Doe", "1990-01-01")
```

## Custom Metadata

```python
from fhir_synth.rule_engine import MetaConfig

meta = MetaConfig(
    security=[{
        "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
        "code": "R",
        "display": "Restricted",
    }],
    tag=[{"system": "http://example.org/tags", "code": "synthetic-data"}],
    profile=["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"],
    source="http://example.org/fhir-synth",
)
```

