# Python API

Use FHIR Synth as a library in your Python code.

## LLM Providers

```python
from fhir_synth.llm import get_provider

# OpenAI (default)
llm = get_provider("gpt-4")

# Anthropic Claude
llm = get_provider("claude-3-5-sonnet-20241022")

# AWS Bedrock with named profile
llm = get_provider(
    "bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
    aws_profile="my-profile",
    aws_region="us-east-1",
)

# AWS Bedrock (relies on env vars / default profile)
llm = get_provider("bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0")

# Google Gemini
llm = get_provider("gemini/gemini-pro")

# Mock provider (no API key needed — for testing)
llm = get_provider("mock")
```

## Code Generation

```python
from fhir_synth.llm import get_provider
from fhir_synth.code_generator import CodeGenerator, get_executor

# Set up LLM provider
llm = get_provider("gpt-4")  # or "mock" for testing

# Generate and execute code (default: smolagents local executor)
code_gen = CodeGenerator(llm)
code = code_gen.generate_code_from_prompt("Create 20 diabetic patients with HbA1c observations")
resources = code_gen.execute_generated_code(code)

# Use a different executor backend
executor = get_executor("docker")
code_gen = CodeGenerator(llm, executor=executor)
resources = code_gen.execute_generated_code(code)

# Apply custom metadata to generated resources
from fhir_synth.code_generator import CodeGenerator

resources = CodeGenerator.apply_metadata_to_resources(
    resources,
    security=[{
        "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
        "code": "N",
        "display": "Normal",
    }],
    tag=[{"system": "http://example.org/tags", "code": "synthetic-data"}],
    profile=["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"],
    source="http://example.org/fhir-synth",
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

## Executor Backends

```python
from fhir_synth.code_generator import get_executor, LocalSmolagentsExecutor, DockerSandboxExecutor, E2BExecutor, BlaxelExecutor

# Local smolagents executor (default — AST-level secure interpreter)
executor = get_executor("local")

# Docker sandbox (requires Docker daemon)
executor = get_executor("docker")

# E2B cloud sandbox
executor = get_executor("e2b")  # requires E2B_API_KEY env var

# Blaxel cloud sandbox
executor = get_executor("blaxel")

# Use with CodeGenerator
code_gen = CodeGenerator(llm, executor=executor)
```

## Two-Stage DSPy Pipeline

The optional DSPy pipeline splits generation into two stages for higher quality output:

- **Stage 1 — Clinical Planning**: prompt + skills → structured `ClinicalPlan` (Pydantic model)
- **Stage 1.5 — Dependency Enrichment**: auto-adds missing resource companions (Practitioner, Organization, etc.)
- **Stage 2 — Code Synthesis**: `ClinicalPlan` + FHIR guidelines → Python code → FHIR resources

```bash
pip install 'fhir-synth[dspy]'
```

```python
from fhir_synth.llm import get_provider
from fhir_synth.pipeline.pipeline import TwoStagePipeline

# Build and run the pipeline
llm = get_provider("gpt-4")
pipeline = TwoStagePipeline.default(llm_provider=llm)
result = pipeline.run("5 diabetic patients with HbA1c observations")

# Access results
print(f"Plan: {len(result.plan.patients)} patient(s)")
print(f"Resources: {len(result.resources)}")
print(f"Quality: {result.report.overall_score:.2f} ({result.report.grade})")
print(f"Code:\n{result.code[:200]}...")

# Use a compiled (optimized) program
pipeline = TwoStagePipeline.from_compiled(
    compiled_path=Path("optimized_pipeline.json"),
    llm_provider=llm,
)
result = pipeline.run("3 patients with hypertension")
```

### DSPy Optimization

Optimize the pipeline's prompts using DSPy's BootstrapFewShot:

```python
import dspy
from fhir_synth.pipeline.pipeline import TwoStagePipeline
from fhir_synth.pipeline.evaluator import GenerationEvaluator
from fhir_synth.pipeline.dspy_modules import FHIRSynthProgram, configure_dspy_lm

# Configure DSPy
configure_dspy_lm(model="gpt-4o")

# Build composite program for optimization
guidelines = TwoStagePipeline.default(llm).build_guidelines()  # or use FHIRGuidelinesBuilder
program = FHIRSynthProgram(fhir_guidelines=guidelines)
evaluator = GenerationEvaluator()

# Create training examples (just prompts — no labels needed)
trainset = [
    dspy.Example(prompt="3 diabetic patients with HbA1c").with_inputs("prompt"),
    dspy.Example(prompt="2 patients with hypertension on Lisinopril").with_inputs("prompt"),
]

# Optimize
optimizer = dspy.BootstrapFewShot(metric=evaluator.dspy_metric, max_bootstrapped_demos=3)
compiled = optimizer.compile(program, trainset=trainset)
dspy.save(compiled, "optimized_pipeline.json")
```

Or use the CLI:

```bash
fhir-synth optimize --optimizer miprov2 --provider deepseek/deepseek-chat --auto medium
```

## FHIR Validation

Validate resources offline using `fhir.resources` Pydantic models:

```python
from fhir_synth.code_generator.fhir_validation import (
    validate_resources, validate_references, repair_references
)
from fhir_synth.code_generator.us_core_validation import validate_us_core

# Pydantic model validation (required fields, types, cardinality)
vr = validate_resources(resources)
print(f"{vr.valid}/{vr.total} valid ({vr.pass_rate:.0%})")

# Reference integrity (cross-resource references)
ref_errors = validate_references(resources)
for err in ref_errors:
    print(f"  {err['resourceType']}/{err['id']}: {err['errors']}")

# Auto-repair broken references
resources, repair_report = repair_references(resources)
print(f"Repaired {repair_report['repaired']} reference(s)")

# US Core compliance (must-support fields)
ucr = validate_us_core(resources)
print(f"US Core: {ucr.compliance_rate:.0%} compliant")
```

## Quality Evaluation

Use the composable evaluator for weighted quality scoring:

```python
from fhir_synth.pipeline.evaluator import GenerationEvaluator

evaluator = GenerationEvaluator()
report = evaluator.evaluate(resources)

print(f"Overall: {report.overall_score:.2f} ({report.grade})")
for ms in report.metric_scores:
    print(f"  {ms.name}: {ms.score:.2f} (weight: {ms.weight})")
```

