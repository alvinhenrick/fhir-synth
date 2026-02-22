# FHIR Synth — Architecture
## System Overview
```mermaid
graph TB
    subgraph UI["🖥️ User Interface"]
        CLI["<b>CLI</b> (Typer)<br/>generate · rules · codegen · bundle"]
        API["<b>Python API</b><br/>CodeGenerator · RuleEngine<br/>BundleBuilder · FHIRResourceFactory"]
    end
    subgraph CORE["⚙️ Core Modules"]
        CG["<b>code_generator.py</b><br/>CodeGenerator<br/>PromptToRulesConverter"]
        RE["<b>rule_engine.py</b><br/>RuleEngine<br/>Rule · RuleSet · GenerationRules"]
        BB["<b>bundle_builder.py</b><br/>BundleBuilder · BundleManager"]
        FU["<b>fhir_utils.py</b><br/>FHIRResourceFactory<br/>BundleFactory"]
        FS["<b>fhir_spec.py</b><br/>Auto-discovery of all<br/>141 R4B resource types"]
    end
    subgraph LLM_LAYER["🤖 LLM Layer"]
        LLM["<b>llm.py</b><br/>LLMProvider · MockLLMProvider<br/>get_provider()"]
        LITELLM["<b>LiteLLM</b><br/>OpenAI · Anthropic · Bedrock<br/>Azure · 100+ providers"]
    end
    subgraph FHIR["🏥 FHIR Foundation"]
        FR["<b>fhir.resources</b> (R4B)<br/>Pydantic models for all<br/>FHIR resource types"]
    end
    CLI --> CG
    CLI --> RE
    CLI --> BB
    API --> CG
    API --> RE
    API --> BB
    API --> FU
    CG --> LLM
    CG --> FS
    RE --> FS
    BB --> RE
    BB --> FS
    FU --> FS
    LLM --> LITELLM
    FS --> FR
    FU --> FR
    style UI fill:#1a1a2e,stroke:#16213e,color:#e0e0e0
    style CORE fill:#0f3460,stroke:#16213e,color:#e0e0e0
    style LLM_LAYER fill:#533483,stroke:#16213e,color:#e0e0e0
    style FHIR fill:#2b580c,stroke:#16213e,color:#e0e0e0
    style CLI fill:#4a9eff,stroke:#2980b9,color:#fff
    style API fill:#4a9eff,stroke:#2980b9,color:#fff
    style CG fill:#e67e22,stroke:#d35400,color:#fff
    style RE fill:#e67e22,stroke:#d35400,color:#fff
    style BB fill:#e67e22,stroke:#d35400,color:#fff
    style FU fill:#e67e22,stroke:#d35400,color:#fff
    style FS fill:#2ecc71,stroke:#27ae60,color:#fff
    style LLM fill:#e74c3c,stroke:#c0392b,color:#fff
    style LITELLM fill:#9b59b6,stroke:#8e44ad,color:#fff
    style FR fill:#27ae60,stroke:#1e8449,color:#fff
```
---
## End-to-End Data Flow — `generate` Command
```mermaid
sequenceDiagram
    autonumber
    participant U as 👤 User
    participant CLI as 🖥️ CLI
    participant CG as ⚙️ CodeGenerator
    participant LLM as 🤖 LLMProvider
    participant EX as 🔒 Sandbox Executor
    participant BB as 📦 BundleBuilder
    participant F as 💾 File
    U->>CLI: fhir-synth generate "10 diabetic patients" -o out.json
    CLI->>CG: generate_code_from_prompt(prompt)
    CG->>LLM: generate_text(system_prompt, user_prompt)
    LLM-->>CG: Python code (fhir.resources)
    CG->>CG: _extract_code() — strip markdown fences
    CG-->>CLI: code string
    CLI->>CG: execute_generated_code(code)
    CG->>CG: validate_code() — compile check
    CG->>EX: exec(code) → generate_resources()
    alt ❌ Execution fails
        EX-->>CG: error / traceback
        CG->>LLM: _retry_with_error(code, error)
        LLM-->>CG: fixed code
        CG->>EX: exec(fixed_code)
    end
    EX-->>CG: list[dict] resources
    CG-->>CLI: resources
    CLI->>BB: add_resources(resources)
    CLI->>BB: build()
    BB-->>CLI: FHIR Bundle dict
    CLI->>F: write JSON
    CLI-->>U: ✓ Bundle with N entries → out.json
```
---
## Three Generation Workflows
```mermaid
graph LR
    subgraph W1["🔧 1 · Code Generation (primary)"]
        P1["📝 Prompt"] --> LLM1["🤖 LLM"]
        LLM1 --> CODE["🐍 Python Code"]
        CODE --> VAL["✅ Validate"]
        VAL --> EXEC["▶️ Execute"]
        EXEC --> RES1["📋 Resources"]
    end
    subgraph W2["📐 2 · Rule-Based Generation"]
        P2["📝 Prompt"] --> LLM2["🤖 LLM"]
        LLM2 --> RULES["📜 Rules JSON"]
        RULES --> RENG["⚙️ RuleEngine"]
        RENG --> RES2["📋 Resources"]
    end
    subgraph W3["📦 3 · Direct Bundle"]
        NDJSON["📄 NDJSON"] --> BB2["📦 BundleBuilder"]
        EMPI["🔗 EMPI"] --> BB2
        BB2 --> RES3["📋 Resources"]
    end
    RES1 --> BUNDLE["🏥 FHIR R4B Bundle"]
    RES2 --> BUNDLE
    RES3 --> BUNDLE
    style W1 fill:#0d47a1,stroke:#1565c0,color:#e0e0e0
    style W2 fill:#4a148c,stroke:#6a1b9a,color:#e0e0e0
    style W3 fill:#1b5e20,stroke:#2e7d32,color:#e0e0e0
    style BUNDLE fill:#e65100,stroke:#bf360c,color:#fff
```
---
## Module Dependency Graph
```mermaid
graph TD
    CLI["🖥️ <b>cli.py</b><br/>Typer commands"]
    CG["⚙️ <b>code_generator.py</b><br/>LLM code gen + execution"]
    RE["📐 <b>rule_engine.py</b><br/>Declarative rules + EMPI"]
    BB["📦 <b>bundle_builder.py</b><br/>Bundle construction"]
    FU["🏗️ <b>fhir_utils.py</b><br/>Resource factory"]
    FS["🔍 <b>fhir_spec.py</b><br/>Spec auto-discovery"]
    LLM["🤖 <b>llm.py</b><br/>LLM providers"]
    FR["🏥 <b>fhir.resources.R4B</b>"]
    LITE["🔌 <b>litellm</b>"]
    CLI --> CG
    CLI --> RE
    CLI --> BB
    CLI --> LLM
    CG --> LLM
    CG --> FS
    BB --> RE
    BB --> FS
    RE --> FS
    FU --> FS
    FS --> FR
    LLM --> LITE
    style CLI fill:#4a9eff,stroke:#2980b9,color:#fff
    style CG fill:#e67e22,stroke:#d35400,color:#fff
    style RE fill:#e67e22,stroke:#d35400,color:#fff
    style BB fill:#e67e22,stroke:#d35400,color:#fff
    style FU fill:#e67e22,stroke:#d35400,color:#fff
    style FS fill:#2ecc71,stroke:#27ae60,color:#fff
    style LLM fill:#e74c3c,stroke:#c0392b,color:#fff
    style FR fill:#9b59b6,stroke:#8e44ad,color:#fff
    style LITE fill:#9b59b6,stroke:#8e44ad,color:#fff
```
---
## Class Diagram
```mermaid
classDiagram
    direction LR
    class Rule {
        <<Pydantic Model>>
        +name : str
        +description : str
        +conditions : dict
        +actions : dict
        +weight : float
    }
    class RuleSet {
        <<Pydantic Model>>
        +resource_type : str
        +description : str
        +rules : list~Rule~
        +default_rule : Rule?
        +bundle_config : dict
    }
    class GenerationRules {
        <<dataclass>>
        +population : dict
        +rules_by_type : dict~str, list~Rule~~
        +add_rules(resource_type, rules)
        +get_rules(resource_type) list~Rule~
        +resource_types : list~str~
        +to_dict() dict
        +from_dict(data)$ GenerationRules
    }
    class RuleEngine {
        +rulesets : dict~str, RuleSet~
        +executors : dict
        +register_ruleset(ruleset)
        +register_executor(type, fn)
        +execute(type, context, count) list~dict~
        +generate_bundle(type, resources) dict
        +generate_empi_resources(persons, systems)$ list~dict~
    }
    class CodeGenerator {
        +llm : LLMProvider
        +max_retries : int
        +generate_code_from_prompt(prompt) str
        +generate_rules_from_prompt(prompt) dict
        +generate_bundle_code(types, count) str
        +validate_code(code) bool
        +execute_generated_code(code) list~dict~
    }
    class PromptToRulesConverter {
        +llm : LLMProvider
        +code_gen : CodeGenerator
        +convert_prompt_to_rules(prompt) dict
        +convert_prompt_to_code(prompt) str
        +extract_resource_types(prompt) list~str~
    }
    class BundleBuilder {
        +bundle_type : str
        +entries : list~dict~
        +add_resource(resource, method, url)
        +add_resources(resources, method)
        +build() dict
        +build_with_relationships(by_type) dict
        +clear()
    }
    class BundleManager {
        +rule_engine : RuleEngine
        +create_bundle_from_rules(rules, ctx) dict
        +create_multi_patient_bundle(count) dict
        +validate_bundle(bundle) tuple
    }
    class FHIRResourceFactory {
        <<static methods>>
        +create_resource(type, data)$ BaseModel
        +create_patient(id, given, family)$ BaseModel
        +create_condition(id, code, patient_id)$ BaseModel
        +create_observation(id, code, patient_id)$ BaseModel
        +create_medication_request(id, code, patient_id)$ BaseModel
        +create_bundle(type, entries)$ BaseModel
        +from_dict(type, data)$ BaseModel
        +to_dict(resource)$ dict
    }
    class BundleFactory {
        +bundle_type : str
        +entries : list~dict~
        +add_resource(resource, method)
        +add_resources(resources, method)
        +build() BaseModel
        +build_dict() dict
        +clear()
    }
    class LLMProvider {
        +model : str
        +api_key : str?
        +generate_text(system, prompt) str
        +generate_json(system, prompt) dict
    }
    class MockLLMProvider {
        +response : str
        +generate_text(system, prompt) str
        +generate_json(system, prompt) dict
    }
    RuleSet *-- Rule : contains
    RuleEngine o-- RuleSet : manages
    GenerationRules o-- Rule : organizes
    BundleManager o-- RuleEngine : delegates to
    CodeGenerator o-- LLMProvider : uses
    PromptToRulesConverter o-- CodeGenerator : wraps
    MockLLMProvider --|> LLMProvider : extends
    BundleFactory ..> FHIRResourceFactory : uses
```
---
## FHIR Resource Relationships
```mermaid
graph TD
    subgraph EMPI["🔗 EMPI Linkage"]
        Person["<b>Person</b>"] -->|"1..*"| Patient["<b>Patient</b>"]
        Patient -->|"0..1"| Organization["<b>Organization</b><br/>(managing)"]
    end
    subgraph CLINICAL["🏥 Clinical Data"]
        Patient -->|"0..*"| Encounter["<b>Encounter</b>"]
        Patient -->|"0..*"| Condition["<b>Condition</b><br/>ICD-10"]
        Patient -->|"0..*"| Observation["<b>Observation</b><br/>LOINC"]
        Patient -->|"0..*"| MedReq["<b>MedicationRequest</b><br/>RxNorm"]
        Patient -->|"0..*"| Procedure["<b>Procedure</b><br/>SNOMED/CPT"]
        Patient -->|"0..*"| DiagReport["<b>DiagnosticReport</b>"]
    end
    subgraph ENCOUNTER_REFS["📋 Encounter Context"]
        Encounter -->|"0..*"| Condition
        Encounter -->|"0..*"| Observation
        Encounter -->|"0..*"| Procedure
        Encounter -->|"0..1"| Practitioner["<b>Practitioner</b>"]
        Encounter -->|"0..1"| Location["<b>Location</b>"]
    end
    subgraph BUNDLE["📦 Bundle"]
        B_TYPE["type: transaction | batch<br/>collection | searchset | history"]
        B_ENTRY["entry[]"]
        B_RES["resource"]
        B_REQ["request {method, url}"]
        B_URL["fullUrl"]
        B_TYPE --- B_ENTRY
        B_ENTRY --- B_RES
        B_ENTRY --- B_REQ
        B_ENTRY --- B_URL
    end
    style EMPI fill:#1a237e,stroke:#283593,color:#e0e0e0
    style CLINICAL fill:#004d40,stroke:#00695c,color:#e0e0e0
    style ENCOUNTER_REFS fill:#263238,stroke:#37474f,color:#e0e0e0
    style BUNDLE fill:#bf360c,stroke:#d84315,color:#e0e0e0
    style Person fill:#e74c3c,stroke:#c0392b,color:#fff
    style Patient fill:#3498db,stroke:#2980b9,color:#fff
    style Organization fill:#f39c12,stroke:#e67e22,color:#fff
    style Encounter fill:#1abc9c,stroke:#16a085,color:#fff
    style Practitioner fill:#95a5a6,stroke:#7f8c8d,color:#fff
    style Location fill:#95a5a6,stroke:#7f8c8d,color:#fff
```
---
## Self-Healing Code Execution
```mermaid
flowchart TD
    A["🤖 LLM generates<br/>Python code"] --> B{"✅ Syntax<br/>valid?"}
    B -->|No| C["📤 Send error<br/>to LLM"]
    B -->|Yes| D["🔒 Execute in<br/>sandbox"]
    D --> E{"✅ Execution<br/>succeeds?"}
    E -->|Yes| F["✓ Return<br/>resources"]
    E -->|No| G{"🔄 Retries<br/>left?"}
    G -->|"Yes (max 2)"| C
    G -->|No| H["✗ Raise<br/>RuntimeError"]
    C --> I["🤖 LLM returns<br/>fixed code"]
    I --> B
    style A fill:#3498db,stroke:#2980b9,color:#fff
    style B fill:#f39c12,stroke:#e67e22,color:#fff
    style C fill:#e74c3c,stroke:#c0392b,color:#fff
    style D fill:#2ecc71,stroke:#27ae60,color:#fff
    style E fill:#f39c12,stroke:#e67e22,color:#fff
    style F fill:#2ecc71,stroke:#27ae60,color:#fff
    style G fill:#9b59b6,stroke:#8e44ad,color:#fff
    style H fill:#c0392b,stroke:#922b21,color:#fff
    style I fill:#3498db,stroke:#2980b9,color:#fff
```
---
## FHIR Spec Auto-Discovery
```mermaid
flowchart LR
    subgraph IMPORT["⚡ Import Time (instant)"]
        SCAN["📂 Scan<br/>fhir.resources.R4B<br/>filesystem"] --> FILTER["🔍 Filter out<br/>data types<br/>(60+ excluded)"]
        FILTER --> MAP["🗂️ _MODULE_MAP<br/>{ClassName: module}<br/>~141 types"]
    end
    subgraph DEMAND["💤 On Demand (cached)"]
        MAP --> GRC["get_resource_class()"]
        GRC --> INTRO["_introspect()"]
        INTRO --> META["ResourceMeta"]
        META --> REQ["required_fields"]
        META --> OPT["optional_fields"]
        META --> REF["reference_fields"]
    end
    subgraph CONSUMERS["🔌 Consumers"]
        REQ --> CG2["CodeGenerator"]
        REQ --> RE2["RuleEngine"]
        OPT --> BB2["BundleBuilder"]
        REF --> FU2["FHIRResourceFactory"]
    end
    style IMPORT fill:#0d47a1,stroke:#1565c0,color:#e0e0e0
    style DEMAND fill:#4a148c,stroke:#6a1b9a,color:#e0e0e0
    style CONSUMERS fill:#1b5e20,stroke:#2e7d32,color:#e0e0e0
```
---
## Processing Pipeline
```mermaid
graph TD
    subgraph S1["1 · 📥 Input"]
        PROMPT["User prompt<br/>(natural language)"]
        CONFIG[".env file<br/>(API keys)"]
        FLAGS["CLI flags<br/>(--provider, --empi, --out)"]
    end
    subgraph S2["2 · 🤖 Generation"]
        LLM_CALL["LLM call<br/>(system + user prompt)"]
        EXTRACT["Code extraction<br/>(strip markdown fences)"]
        VALIDATE["Syntax validation<br/>(compile check)"]
        EXECUTE["Sandboxed execution<br/>(restricted builtins)"]
        SELFHEAL["Self-healing retry<br/>(send error back to LLM)"]
    end
    subgraph S3["3 · 📦 Bundling"]
        COLLECT["Collect resources"]
        REFLINK["Reference linking<br/>(Patient refs)"]
        WRAP["Wrap in Bundle<br/>(transaction/batch)"]
        BVAL["Bundle validation"]
    end
    subgraph S4["4 · 💾 Output"]
        JSON["JSON serialization"]
        FILE["File output"]
        FEEDBACK["User feedback<br/>(✓ Bundle with N entries)"]
    end
    PROMPT --> LLM_CALL
    CONFIG --> LLM_CALL
    FLAGS --> LLM_CALL
    LLM_CALL --> EXTRACT --> VALIDATE --> EXECUTE
    EXECUTE -->|"❌ fail"| SELFHEAL --> LLM_CALL
    EXECUTE -->|"✅ ok"| COLLECT
    COLLECT --> REFLINK --> WRAP --> BVAL
    BVAL --> JSON --> FILE --> FEEDBACK
    style S1 fill:#1a237e,stroke:#283593,color:#e0e0e0
    style S2 fill:#b71c1c,stroke:#c62828,color:#e0e0e0
    style S3 fill:#004d40,stroke:#00695c,color:#e0e0e0
    style S4 fill:#e65100,stroke:#ef6c00,color:#e0e0e0
```
---
## LLM Provider Integration
```mermaid
graph TD
    GP["get_provider(name)"]
    GP -->|"mock"| MOCK["🧪 MockLLMProvider<br/>(deterministic, no API key)"]
    GP -->|"gpt-4"| GPT["🟢 OpenAI<br/>OPENAI_API_KEY"]
    GP -->|"claude-3-*"| CLAUDE["🟣 Anthropic<br/>ANTHROPIC_API_KEY"]
    GP -->|"bedrock/*"| BEDROCK["🟠 AWS Bedrock<br/>AWS credentials"]
    GP -->|"azure/*"| AZURE["🔵 Azure OpenAI<br/>AZURE_API_KEY"]
    GP -->|"any other"| OTHER["⚪ 100+ providers<br/>via LiteLLM"]
    MOCK --> GEN_TEXT["generate_text()"]
    GPT --> GEN_TEXT
    CLAUDE --> GEN_TEXT
    BEDROCK --> GEN_TEXT
    AZURE --> GEN_TEXT
    OTHER --> GEN_TEXT
    GEN_TEXT --> GEN_JSON["generate_json()"]
    style GP fill:#4a9eff,stroke:#2980b9,color:#fff
    style MOCK fill:#95a5a6,stroke:#7f8c8d,color:#fff
    style GPT fill:#2ecc71,stroke:#27ae60,color:#fff
    style CLAUDE fill:#9b59b6,stroke:#8e44ad,color:#fff
    style BEDROCK fill:#e67e22,stroke:#d35400,color:#fff
    style AZURE fill:#3498db,stroke:#2980b9,color:#fff
    style OTHER fill:#bdc3c7,stroke:#95a5a6,color:#2c3e50
```
---
## File Structure
```
fhir-synth/
├── src/fhir_synth/
│   ├── __init__.py            # Package exports, .env loading
│   ├── cli.py                 # Typer CLI: generate, rules, codegen, bundle
│   ├── code_generator.py      # CodeGenerator, PromptToRulesConverter
│   ├── rule_engine.py         # Rule, RuleSet, RuleEngine, GenerationRules
│   ├── bundle_builder.py      # BundleBuilder, BundleManager
│   ├── fhir_utils.py          # FHIRResourceFactory, BundleFactory
│   ├── fhir_spec.py           # Auto-discovery of 141 R4B resource types
│   └── llm.py                 # LLMProvider, MockLLMProvider, get_provider()
│
├── tests/
│   ├── test_bundle_builder.py
│   ├── test_code_generator.py
│   ├── test_empi.py
│   ├── test_fhir_spec.py
│   ├── test_fhir_utils.py
│   ├── test_llm.py
│   └── test_rule_engine.py
│
├── pyproject.toml             # Hatch build, ruff, mypy, pytest config
├── README.md                  # Usage docs and quick start
└── ARCHITECTURE.md            # This file
```
