# LLM Framework Analysis for FHIR-Synth

## Current Implementation

FHIR-Synth currently uses a **direct LLM prompting** approach with:
- System prompts with detailed instructions
- Self-healing retry mechanism (up to 3 attempts)
- Basic error feedback loop
- Import validation and auto-fixing

## Should We Use DSPy, LangChain, or LlamaIndex?

### DSPy (Declarative Self-improving Python)

**Pros:**
- ✅ **Perfect fit for code generation**: DSPy excels at structured output tasks
- ✅ **Chain-of-thought optimization**: Automatically adds reasoning steps
- ✅ **Few-shot learning**: Can optimize prompts with example code snippets
- ✅ **Automatic prompt optimization**: Uses `BootstrapFewShot` to improve prompts
- ✅ **Signature-based validation**: Type-safe input/output contracts
- ✅ **Metric-driven**: Can optimize for "valid executable code" as a metric

**Cons:**
- ❌ Additional dependency weight
- ❌ Learning curve for the team
- ❌ May be overkill for single-step code generation

**Best Use Cases:**
- Multi-step reasoning (plan → code → validate → fix)
- When you have training examples to optimize prompts
- Complex chains with multiple LLM calls

### LangChain

**Pros:**
- ✅ Rich ecosystem of integrations
- ✅ Good for RAG (retrieval-augmented generation)
- ✅ Agent frameworks with tools

**Cons:**
- ❌ **Heavy dependency**: Lots of sub-packages
- ❌ Frequent breaking changes
- ❌ Overhead for simple prompt → code tasks
- ❌ Not specialized for code generation

**Verdict:** ❌ **Not recommended** - Too heavyweight for our use case

### LlamaIndex

**Pros:**
- ✅ Excellent for document search and RAG
- ✅ Good for querying FHIR spec documentation

**Cons:**
- ❌ Not designed for code generation
- ❌ Better suited for Q&A over knowledge bases

**Verdict:** ❌ **Not needed** - We don't need RAG for code generation

---

## Recommendation: Hybrid Approach

### Current Approach (Keep)
Your current implementation is actually quite good:
1. ✅ Simple and maintainable
2. ✅ Self-healing with error feedback
3. ✅ Import validation and auto-fixing
4. ✅ Direct control over prompts
5. ✅ LiteLLM for provider flexibility

### Suggested Improvements (Without DSPy)

#### 1. Add Chain-of-Thought Manually
```python
# In prompts.py
SYSTEM_PROMPT = """...(existing)...

**THINK STEP-BY-STEP:**
1. Understand the requirement and identify resource types
2. Plan the data structure and relationships
3. Choose appropriate clinical codes
4. Write imports with correct module paths
5. Implement generate_resources() function
6. Validate relationships and references
"""
```

#### 2. Add Few-Shot Examples
```python
FEW_SHOT_EXAMPLES = """
EXAMPLE 1:
Requirement: "5 patients with hypertension"
Code:
```python
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.reference import Reference
from uuid import uuid4
from datetime import date, timedelta
import random

def generate_resources() -> list[dict]:
    resources = []
    names = [("John", "Doe"), ("Jane", "Smith"), ...]
    
    for i, (first, last) in enumerate(names[:5]):
        patient_id = str(uuid4())
        
        # Patient
        patient = Patient(
            id=patient_id,
            name=[{"given": [first], "family": last}],
            gender=random.choice(["male", "female"]),
            birthDate=str(date(1950 + i*5, 1, 1))
        )
        resources.append(patient.model_dump(exclude_none=True))
        
        # Condition: Hypertension
        condition = Condition(
            id=str(uuid4()),
            subject=Reference(reference=f"Patient/{patient_id}"),
            code=CodeableConcept(
                coding=[Coding(
                    system="http://hl7.org/fhir/sid/icd-10-cm",
                    code="I10",
                    display="Essential hypertension"
                )]
            ),
            clinicalStatus=CodeableConcept(
                coding=[Coding(
                    system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                    code="active"
                )]
            )
        )
        resources.append(condition.model_dump(exclude_none=True))
    
    return resources
```
"""
```

#### 3. Add Validation Metrics
```python
def calculate_code_quality_score(code: str, resources: list[dict]) -> float:
    """Score generated code quality (0.0 to 1.0)."""
    score = 1.0
    
    # Deduct for missing best practices
    if "uuid4" not in code:
        score -= 0.2
    if "model_dump(exclude_none=True)" not in code:
        score -= 0.2
    if not any(r.get("resourceType") == "Patient" for r in resources):
        score -= 0.3
    
    # Check for proper references
    patients = [r for r in resources if r.get("resourceType") == "Patient"]
    clinical = [r for r in resources if r.get("resourceType") in 
                ["Condition", "Observation", "MedicationRequest"]]
    
    if clinical and patients:
        # Check if clinical resources reference patients
        has_refs = any("subject" in r or "patient" in r for r in clinical)
        if not has_refs:
            score -= 0.3
    
    return max(0.0, score)
```

---

## When to Consider DSPy

Use DSPy **only if**:
1. ✅ You have 50+ example prompt/code pairs to train on
2. ✅ You need multi-step reasoning (decompose prompt → plan → code → test)
3. ✅ You want automatic prompt optimization
4. ✅ Current approach fails >20% of the time

### DSPy Implementation Preview

If you decide to use DSPy later:

```python
import dspy

class CodeGenerationSignature(dspy.Signature):
    """Generate FHIR R4B Python code from requirements."""
    requirement = dspy.InputField(desc="Natural language description")
    code = dspy.OutputField(desc="Python code with generate_resources()")

class FHIRCodeGenerator(dspy.Module):
    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(CodeGenerationSignature)
    
    def forward(self, requirement: str) -> str:
        result = self.generate(requirement=requirement)
        return result.code

# Optimization with examples
optimizer = dspy.BootstrapFewShot(
    metric=lambda example, pred: validate_and_score(pred.code),
    max_bootstrapped_demos=5
)
optimized_generator = optimizer.compile(FHIRCodeGenerator(), trainset=examples)
```

---

## Final Recommendation

### ✅ **Keep Current Approach + Manual Enhancements**

**Do This:**
1. ✅ Add chain-of-thought reasoning to system prompt
2. ✅ Include 2-3 few-shot examples in prompt
3. ✅ Add code quality scoring
4. ✅ Log successful generations for future optimization
5. ✅ Keep current self-healing mechanism

**Don't Add:**
- ❌ LangChain (too heavy)
- ❌ LlamaIndex (not needed)
- ❌ DSPy (not yet - wait until you have training data)

**Consider DSPy Later If:**
- You collect 100+ successful prompt/code examples
- You want to experiment with prompt optimization
- Current success rate drops below 80%

---

## Conclusion

Your current implementation is **solid and appropriate** for the problem. The key improvements needed are:
1. Better prompts (chain-of-thought, few-shot examples)
2. Quality metrics for generated code
3. Logging successful patterns

Adding DSPy now would be **premature optimization**. Focus on collecting data and improving prompts first, then revisit DSPy in 6 months when you have a training dataset.

