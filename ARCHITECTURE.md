# FHIR Synth Architecture - Visual Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                         │
│                                                             │
│  CLI Commands         │      Python API                    │
│  ─────────────────    │      ──────────                    │
│  fhir-synth rules     │      from fhir_synth import        │
│  fhir-synth codegen   │        RuleEngine                  │
│  fhir-synth bundle    │        CodeGenerator               │
│                       │        BundleBuilder               │
│                       │        FHIRResourceFactory         │
└──────┬────────────────┴──────────────────┬──────────────────┘
       │                                   │
       ▼                                   ▼
┌────────────────────────┐    ┌─────────────────────────────┐
│   CLI Layer            │    │   Core Modules Layer        │
│   (cli.py)             │    │                             │
│                        │    │  • rule_engine.py           │
│  • rules               │    │  • code_generator.py        │
│  • codegen             │    │  • bundle_builder.py        │
│  • bundle              │    │  • fhir_utils.py            │
└────────────┬───────────┘    └──────────────┬──────────────┘
             │                               │
             └───────────────┬───────────────┘
                             │
                    ┌────────▼──────────┐
                    │  Execution Layer  │
                    │                   │
                    │ • Rule Engine     │
                    │ • Code Generator  │
                    │ • LLM Provider    │
                    │ • Validators      │
                    └────────┬──────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌────────────┐  ┌──────────┐  ┌──────────────┐
        │ FHIR R4B   │  │ Bundle   │  │ LLM Providers│
        │ Resources  │  │ Builder  │  │              │
        │            │  │          │  │ • OpenAI     │
        │ • Patient  │  │ • Bundle │  │ • Anthropic  │
        │ • Condition│  │ • Entry  │  │ • Bedrock    │
        │ • Observation  │ • Ref   │  │ • Mock       │
        │ • ...      │  │          │  │ • ... 100+   │
        └────────────┘  └──────────┘  └──────────────┘
```

## Data Flow

### Workflow 1: Rule-Based Generation
```
User Prompt
    ↓
LLM Provider
    ↓
Rule Definitions (JSON)
    ↓
Rule Engine
    ↓
FHIR Resources
    ↓
Bundle Builder
    ↓
FHIR Bundle (JSON)
```

### Workflow 2: Code Generation
```
User Prompt
    ↓
CodeGenerator
    ↓
LLM Provider (e.g., GPT-4)
    ↓
Python Code
    ↓
Code Validator
    ↓
Code Executor
    ↓
FHIR Resources
    ↓
Bundle Builder
    ↓
FHIR Bundle (JSON)
```

### Workflow 3: Bundle Creation
```
NDJSON File
(Patient, Condition, Observation...)
    ↓
BundleBuilder
    ↓
Reference Linking
    ↓
Bundle Validation
    ↓
FHIR Bundle (JSON)
```

## Module Dependencies

```
┌─────────────────────────────────────────────────────┐
│                  CLI Layer (cli.py)                 │
│  Provides user interface for all commands           │
└──────────┬──────────────────────────────────────────┘
           │
      ┌────┴───┬──────────┬──────────┐
      │         │          │          │
      ▼         ▼          ▼          ▼
┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│ rule_   │ │ code_    │ │ bundle_  │ │ fhir_    │
│ engine  │ │ generator│ │ builder  │ │ utils    │
└────┬────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │           │            │            │
     ├───────────┼────────────┼────────────┤
     │           │            │            │
     ▼           ▼            ▼            ▼
  ┌────────────────────────────────────────┐
  │     LLM Module (llm.py)                │
  │  - get_provider()                      │
  │  - LLMProvider class                   │
  │  - MockLLMProvider class               │
  └────────────────────────────────────────┘
     │
     ▼
  ┌────────────────────────────────────────┐
  │  External Dependencies                 │
  │  - fhir.resources (R4B)                │
  │  - LiteLLM (100+ LLM providers)        │
  │  - Pydantic (validation)               │
  │  - Typer (CLI framework)               │
  └────────────────────────────────────────┘
```

## Class Hierarchy

```
Rule Engine Module:
│
├── Rule (Pydantic Model)
│   ├── name: str
│   ├── description: str
│   ├── conditions: dict
│   ├── actions: dict
│   └── weight: float
│
├── RuleSet (Pydantic Model)
│   ├── resource_type: str
│   ├── description: str
│   ├── rules: list[Rule]
│   └── bundle_config: dict
│
├── RuleEngine (Executor)
│   ├── register_ruleset()
│   ├── execute()
│   ├── _select_rule()
│   ├── _check_conditions()
│   └── generate_bundle()
│
└── GenerationRules (Container)
    ├── population: dict
    ├── conditions: list[Rule]
    ├── medications: list[Rule]
    ├── observations: list[Rule]
    ├── procedures: list[Rule]
    ├── documents: list[Rule]
    └── custom_rules: dict


Code Generator Module:
│
├── CodeGenerator
│   ├── generate_code_from_prompt()
│   ├── generate_rules_from_prompt()
│   ├── generate_bundle_code()
│   ├── validate_code()
│   ├── execute_generated_code()
│   └── _extract_code()
│
└── PromptToRulesConverter
    ├── convert_prompt_to_rules()
    ├── convert_prompt_to_code()
    └── extract_resource_types()


Bundle Builder Module:
│
├── BundleBuilder
│   ├── add_resource()
│   ├── add_resources()
│   ├── build()
│   ├── build_with_relationships()
│   └── clear()
│
├── BundleManager
│   ├── create_bundle_from_rules()
│   ├── create_multi_patient_bundle()
│   ├── validate_bundle()
│   └── _add_patient_reference()


FHIR Utils Module:
│
├── FHIRResourceFactory
│   ├── create_patient()
│   ├── create_condition()
│   ├── create_observation()
│   ├── create_medication_request()
│   ├── create_bundle()
│   ├── from_dict()
│   └── to_dict()
│
└── BundleFactory
    ├── add_resource()
    ├── add_resources()
    ├── build()
    ├── build_dict()
    └── clear()
```

## Data Types Flow

```
User Input (String)
    │
    ├─→ Rule Engine Flow
    │   └─→ Rule (JSON)
    │       └─→ RuleSet
    │           └─→ Resources (dict)
    │               └─→ FHIR R4B Objects
    │                   └─→ Bundle
    │
    └─→ Code Generator Flow
        └─→ Python Code (str)
            └─→ Validated Code
                └─→ Executed Code
                    └─→ Resources (list[dict])
                        └─→ FHIR R4B Objects
                            └─→ Bundle
```

## Processing Pipeline

```
1. INPUT STAGE
   ├── User Prompt (CLI or API)
   ├── Configuration (YAML/JSON)
   └── LLM Provider Selection

2. PROCESSING STAGE
   ├── LLM Processing
   │  └── Generate Code/Rules
   ├── Code Generation
   │  ├── Code Extraction
   │  ├── Code Validation
   │  └── Code Execution
   └── Resource Generation
      └── Rule Engine Execution

3. TRANSFORMATION STAGE
   ├── Rule Selection
   ├── Condition Matching
   ├── Resource Creation
   └── Reference Linking

4. BUNDLING STAGE
   ├── Bundle Type Selection
   ├── Entry Creation
   ├── Reference Management
   └── Bundle Validation

5. OUTPUT STAGE
   ├── JSON Serialization
   ├── File Writing
   └── User Feedback
```

## Resource Relationships

```
Patient (1) ──references──→ Person (1..1)
  ├─→ Condition (0..*)
  │   ├─→ code (ICD-10)
  │   └─→ status
  │
  ├─→ Observation (0..*)
  │   ├─→ code (LOINC)
  │   ├─→ value
  │   └─→ date
  │
  ├─→ MedicationRequest (0..*)
  │   ├─→ medicationCodeableConcept
  │   ├─→ dosageInstruction
  │   └─→ status
  │
  ├─→ Encounter (0..*)
  │   ├─→ type
  │   └─→ period
  │
  └─→ Organization (managing)
      └─→ identifier

Bundle (container)
  ├─→ entry (0..*)
  │   ├─→ resource
  │   ├─→ request
  │   │   ├─→ method
  │   │   └─→ url
  │   └─→ fullUrl
  │
  └─→ type (transaction|batch|collection|searchset|history)
```

## LLM Integration Points

```
┌─────────────────────────────────────┐
│       LLM Provider Interface         │
│                                     │
│  get_provider(name, api_key)        │
│  ├── "gpt-4" (OpenAI)               │
│  ├── "claude-3-opus" (Anthropic)    │
│  ├── "bedrock/..." (AWS)            │
│  ├── "mock" (Testing)               │
│  └── 100+ others (LiteLLM)          │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│    LLMProvider / MockLLMProvider     │
│                                     │
│  generate_text()                    │
│  generate_json()                    │
└──────────┬──────────────────────────┘
           │
   ┌───────┴────────┐
   │                │
   ▼                ▼
CodeGenerator   PromptToRulesConverter
   │                │
   ├─→ Code Gen     ├─→ Rule Gen
   ├─→ Validate     ├─→ JSON Output
   └─→ Execute      └─→ Dict Output
```

## File Structure

```
fhir-synth/
│
├── src/fhir_synth/
│   ├── __init__.py
│   ├── cli.py ← UPDATED (new commands)
│   │
│   ├── rule_engine.py ← NEW
│   │   ├── Rule
│   │   ├── RuleSet
│   │   ├── RuleEngine
│   │   └── GenerationRules
│   │
│   ├── code_generator.py ← NEW
│   │   ├── CodeGenerator
│   │   └── PromptToRulesConverter
│   │
│   ├── bundle_builder.py ← NEW
│   │   ├── BundleBuilder
│   │   └── BundleManager
│   │
│   ├── fhir_utils.py ← NEW
│   │   ├── FHIRResourceFactory
│   │   ├── BundleFactory
│   │   └── FHIR_RESOURCE_CLASSES
│   │
│   ├── llm.py (existing)
│   ├── generator.py (existing)
│   ├── plan.py (existing)
│   ├── validation.py (existing)
│   ├── writers.py (existing)
│   └── ...
│
├── examples/
│   ├── fhir_resources_usage.py ← NEW
│   └── rule_based_generation.py ← NEW
│
├── README.md ← UPDATED
├── QUICK_REFERENCE.md ← NEW
├── RULE_BASED_GENERATION.md ← NEW
├── START_HERE.md ← NEW
├── IMPLEMENTATION_STATUS.md ← NEW
├── IMPLEMENTATION_CHECKLIST.md ← NEW
│
└── pyproject.toml (dependencies unchanged)
```

---

This architecture provides a clean separation of concerns while allowing deep integration between components for complex synthetic data generation workflows.

