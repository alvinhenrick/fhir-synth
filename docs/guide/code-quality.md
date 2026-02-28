# Code Quality and Robustness

FHIR-Synth includes automated code quality scoring and robust error handling for LLM-generated code.

## Quality Scoring

Every generated code is evaluated against best practices:

```python
from fhir_synth.code_generator import calculate_code_quality_score, print_quality_report

# Score generated code
metrics = calculate_code_quality_score(code, resources)
print_quality_report(metrics)
```

### Quality Checks

| Check | Weight | Description |
|-------|--------|-------------|
| **Uses UUID** | 15% | Code uses `uuid4()` for ID generation |
| **Model Dump** | 20% | All resources call `.model_dump(exclude_none=True)` |
| **Has Function** | 30% | Defines `generate_resources()` function |
| **FHIR R4B** | 10% | Imports from `fhir.resources.R4B` |
| **No Bad Imports** | 20% | Avoids common import errors |
| **Has Patients** | 20% | Includes Patient resources when needed |
| **Has References** | 20% | Clinical resources properly reference patients |

### Scoring Scale

- **A+ (0.95-1.0)**: Excellent - Production ready
- **A (0.90-0.94)**: Very good - Minor improvements needed
- **B (0.80-0.89)**: Good - Some best practices missing
- **C (0.70-0.79)**: Acceptable - Needs improvement
- **F (<0.70)**: Failed - Significant issues

## Error Handling

### Import Validation

Code is validated before execution:

```python
from fhir_synth.code_generator.executor import validate_imports

errors = validate_imports(code)
if errors:
    print(f"Found {len(errors)} import errors:")
    for error in errors:
        print(f"  • {error}")
```

### Auto-Fix Common Errors

Common import mistakes are automatically corrected:

```python
from fhir_synth.code_generator.executor import fix_common_imports

# Before: from fhir.resources.R4B.timingrepeat import TimingRepeat
# After:  from fhir.resources.R4B.timing import TimingRepeat

fixed_code = fix_common_imports(code)
```

### Self-Healing Retry

Failed code is sent back to the LLM for correction (up to 3 attempts):

```python
from fhir_synth.code_generator import CodeGenerator
from fhir_synth.llm import get_provider

llm = get_provider("gpt-4")
generator = CodeGenerator(llm, max_retries=2)

# Auto-retries on failure with error feedback
resources = generator.execute_generated_code(code)
```

## Chain-of-Thought Prompting

The system prompt guides the LLM through structured reasoning:

```
THINK STEP-BY-STEP:
1. Parse requirement → identify resource types needed
2. Plan imports → check correct module paths
3. Design data flow → determine relationships
4. Choose codes → select appropriate ICD-10/LOINC/RxNorm codes
5. Implement function → write generate_resources()
6. Validate → ensure all references are valid
```

## Few-Shot Learning

Examples are provided in prompts to guide generation:

```python
# Example included in every prompt:
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.condition import Condition
from uuid import uuid4

def generate_resources() -> list[dict]:
    resources = []
    patient_id = str(uuid4())
    
    patient = Patient(id=patient_id, ...)
    resources.append(patient.model_dump(exclude_none=True))
    
    condition = Condition(
        subject=Reference(reference=f"Patient/{patient_id}"),
        ...
    )
    resources.append(condition.model_dump(exclude_none=True))
    
    return resources
```

## Debugging Generated Code

### Save Generated Code

```bash
fhir-synth generate "10 patients" -o output.json --save-code generated.py
```

### Enable Quality Scoring

```python
generator = CodeGenerator(llm, enable_scoring=True)
# Logs quality metrics after each generation
```

### Inspect Errors

When generation fails, helpful suggestions are provided:

```
❌ Import error detected
   No module named 'fhir.resources.R4B.timingrepeat'

💡 Suggestions:
   1. Try a more reliable provider: --provider gpt-4
   2. Save and inspect the code: --save-code output.py
   3. The LLM may have used incorrect import paths
```

## Best Practices

### 1. Use Reliable Providers

```bash
# Recommended
fhir-synth generate "..." --provider gpt-4

# Also good
fhir-synth generate "..." --provider claude-3-opus

# Less reliable
fhir-synth generate "..." --provider gpt-3.5-turbo
```

### 2. Save Code for Review

Always save code when testing:

```bash
fhir-synth generate "complex requirement" \
  -o output.json \
  --save-code generated.py \
  --provider gpt-4
```

### 3. Enable Logging

```python
import logging
logging.basicConfig(level=logging.INFO)

# Now CodeGenerator will log quality metrics
generator = CodeGenerator(llm, enable_scoring=True)
```

### 4. Validate Output

```python
from fhir_synth.code_generator import calculate_code_quality_score

metrics = calculate_code_quality_score(code, resources)
if not metrics["passed"]:
    print(f"Quality check failed: {metrics['grade']}")
    print(f"Warnings: {metrics['warnings']}")
```

## Advanced: Collecting Training Data

For future DSPy optimization, collect successful generations:

```python
import json
from pathlib import Path

# After successful generation
if metrics["score"] >= 0.9:
    # Save high-quality examples
    example = {
        "prompt": prompt,
        "code": code,
        "score": metrics["score"],
        "resource_count": len(resources),
    }
    
    with open("training_examples.jsonl", "a") as f:
        f.write(json.dumps(example) + "\n")
```

After collecting 100+ examples, consider using DSPy for prompt optimization.

## Performance Tips

1. **Specific Prompts**: "10 patients with Type 2 diabetes and HbA1c observations"
   - Better than: "some patients with conditions"

2. **Realistic Counts**: Request 5-50 resources
   - Avoid: "1000 patients" (LLM may generate loops incorrectly)

3. **Clear Requirements**: Specify relationships
   - "Each patient should have 3 observations"
   - "Link all conditions to encounters"

4. **Use Metadata Config**: Instead of complex prompts
   ```bash
   --metadata-config config.yaml
   ```

## Troubleshooting

### Issue: Import Errors

**Symptom**: `No module named 'fhir.resources.R4B.xxx'`

**Solution**:
1. Try `--provider gpt-4` (more reliable)
2. Check generated code: `--save-code output.py`
3. Manually fix imports and run the code directly

### Issue: Low Quality Score

**Symptom**: Code score < 0.7

**Solution**:
1. Use better prompts with specific requirements
2. Switch to gpt-4 or claude-3-opus
3. Add few-shot examples to your prompt

### Issue: Wrong Resource Relationships

**Symptom**: Clinical resources don't reference patients

**Solution**:
- Be explicit: "Generate 10 patients, each with 2 conditions linked via subject reference"
- Check quality report warnings

### Issue: No Resources Generated

**Symptom**: Empty resource list

**Solution**:
1. Check if `generate_resources()` function exists
2. Verify it returns a list
3. Save code and inspect for errors

