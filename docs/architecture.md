# Architecture

## System Overview

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff','primaryTextColor':'#1a1a1a','primaryBorderColor':'#94a3b8','lineColor':'#64748b','secondaryColor':'#ffffff','tertiaryColor':'#ffffff','clusterBkg':'#ffffff','clusterBorder':'#cbd5e1'}}}%%
graph TB
    subgraph UI["🖥️ User Interface"]
        CLI["CLI (Typer)<br/>generate · codegen · bundle"]
        API["Python API<br/>CodeGenerator · BundleBuilder<br/>FHIRResourceFactory"]
    end

    subgraph CORE["⚙️ Core Modules"]
        CG["code_generator/<br/>CodeGenerator<br/>prompts · constants · utils"]
        BB["bundle/<br/>BundleBuilder · BundleManager<br/>BundleFactory"]
        FU["fhir_utils/<br/>FHIRResourceFactory<br/>LazyResourceMap"]
        FS["fhir_spec.py<br/>Auto-discovery of all<br/>141 R4B resource types"]
    end

    subgraph EXEC["🔒 Executor Backends (smolagents)"]
        EX_IF["Executor Protocol<br/>execute(code) → ExecutionResult"]
        LOCAL["LocalSmolagentsExecutor<br/>(default — AST-level secure interpreter)"]
        DOCKER["DockerSandboxExecutor<br/>(Docker container via smolagents)"]
        E2B["E2BExecutor<br/>(E2B cloud sandbox via smolagents)"]
        BLAXEL["BlaxelExecutor<br/>(Blaxel cloud sandbox via smolagents)"]
    end

    subgraph LLM_LAYER["🤖 LLM Layer"]
        LLM["llm.py<br/>LLMProvider · MockLLMProvider<br/>get_provider()"]
        LITELLM["LiteLLM<br/>OpenAI · Anthropic · Bedrock<br/>Azure · 100+ providers"]
    end

    subgraph FHIR["🏥 FHIR Foundation"]
        FR["fhir.resources (R4B)<br/>Pydantic models for all<br/>FHIR resource types"]
    end

    CLI -->|uses| CG
    CLI -->|uses| BB
    API -->|uses| CG
    API -->|uses| BB
    API -->|uses| FU

    CG -->|executes via| EX_IF
    EX_IF -.->|implements| LOCAL
    EX_IF -.->|implements| DOCKER
    EX_IF -.->|implements| E2B
    EX_IF -.->|implements| BLAXEL

    CG -->|calls| LLM
    CG -->|introspects| FS
    BB -->|introspects| FS
    FU -->|introspects| FS
    LLM -->|powered by| LITELLM
    FS -->|discovers| FR
    FU -->|creates| FR

    classDef uiStyle fill:#E0F2FE,stroke:#0284c7,stroke-width:3px,color:#1a1a1a
    classDef coreStyle fill:#FEF3C7,stroke:#f59e0b,stroke-width:2px,color:#1a1a1a
    classDef execStyle fill:#DBEAFE,stroke:#3b82f6,stroke-width:2px,color:#1a1a1a
    classDef llmStyle fill:#FCE7F3,stroke:#ec4899,stroke-width:2px,color:#1a1a1a
    classDef fhirStyle fill:#D1FAE5,stroke:#10b981,stroke-width:2px,color:#1a1a1a

    class CLI,API uiStyle
    class CG,BB,FU,FS coreStyle
    class EX_IF,LOCAL,DOCKER,E2B,BLAXEL execStyle
    class LLM,LITELLM llmStyle
    class FR fhirStyle
```

---

## Generate Command — Data Flow

The primary workflow: prompt → LLM → code → safety checks → sandbox exec → smoke test → FHIR Bundle.

```mermaid
sequenceDiagram
    autonumber
    participant U as 👤 User
    participant CLI as 🖥️ CLI
    participant CG as ⚙️ CodeGenerator
    participant LLM as 🤖 LLMProvider
    participant EX as 🔒 Executor<br/>(local│docker│e2b│blaxel)
    participant BB as 📦 BundleBuilder
    participant F as 💾 File

    U->>CLI: fhir-synth generate "10 diabetic patients"
    CLI->>CG: generate_code_from_prompt(prompt)

    Note over CG,LLM: System prompt includes FHIR spec,<br/>sandbox constraints, import guide
    CG->>LLM: generate_text(system_prompt, user_prompt)
    LLM-->>CG: Python code (fhir.resources)
    CG->>CG: extract_code() — strip markdown fences
    CG-->>CLI: code string

    CLI->>CG: execute_generated_code(code)
    CG->>CG: validate_imports() + fix_common_imports()
    CG->>CG: validate_code() — syntax + safety checks

    CG->>EX: execute_code(code)
    Note over EX: Pre-flight: import whitelist + dangerous builtins
    Note over EX: Auto-fix: naive datetime.now() → UTC
    EX->>EX: Subprocess: exec(code) → generate_resources()
    EX->>EX: Enhanced validation: Pydantic strict mode + choice-type [x] checks

    alt ❌ Execution or smoke test fails
        EX-->>CG: error message
        CG->>LLM: build_fix_prompt(code, error)
        LLM-->>CG: fixed code
        CG->>EX: execute_code(fixed_code)
    end

    EX-->>CG: list[dict] resources
    CG-->>CLI: resources

    CLI->>BB: add_resources(resources)
    CLI->>BB: build()
    BB-->>CLI: FHIR Bundle dict

    CLI->>F: write to runs/<name>/ directory
    CLI-->>U: ✓ runs/<name>/ (prompt.txt + .py + .ndjson + patient_*.json with --split)
```

---

## Self-Healing Code Execution

When LLM-generated code fails, the error is automatically sent back to the LLM for correction (up to 2 retries). The fix prompt includes the error, the failing code, the FHIR import guide, and specific hints for common error types.

```mermaid
flowchart TD
    A["🤖 LLM generates Python code"] --> B["🔍 Pre-flight safety checks"]
    B --> B1{"Import whitelist?"}
    B1 -->|"Disallowed import"| FIX["📤 Auto-fix imports or send error to LLM"]
    B1 -->|Pass| B2{"Dangerous builtins?"}
    B2 -->|"eval/exec/open"| REJECT["✗ Reject code"]
    B2 -->|Pass| B3["🔧 Auto-fix naive datetime.now()"]
    B3 --> C["🔒 Execute via chosen backend<br/>(local / docker / e2b / blaxel)"]
    C --> D{"✅ Execution OK?"}
    D -->|"Runtime error"| RETRY
    D -->|Pass| E["🧪 Enhanced FHIR validation"]
    E --> E1{"Non-empty list?"}
    E1 -->|Empty| RETRY
    E1 -->|Pass| E2{"Choice-type [x] conflicts?"}
    E2 -->|Multiple variants set| RETRY
    E2 -->|Pass| E3{"Pydantic model_validate?"}
    E3 -->|ValidationError| RETRY
    E3 -->|Pass| F["✓ Return resources"]

    RETRY{"🔄 Retries left?"}
    RETRY -->|"Yes (max 2)"| FIX2["📤 Send error + code to LLM"]
    RETRY -->|No| H["✗ Raise RuntimeError"]
    FIX2 --> G["🤖 LLM returns fixed code"]
    FIX --> G
    G --> B
```

### Error types handled by self-healing

| Error | Auto-fix | LLM hint |
|---|---|---|
| Wrong fhir.resources import path | `fix_common_imports()` rewrites the import | Import guide with correct module paths |
| `datetime.now()` without timezone | Source rewrite to `datetime.now(timezone.utc)` | "Add timezone offset" |
| Disallowed import (`os`, `socket`, etc.) | — | "Replace with allowed alternative" |
| Pydantic `ValidationError` (required fields, types, cardinality) | — | "Fix the invalid field value or type" |
| Choice-type [x] conflict (e.g. both `deceasedBoolean` and `deceasedAge`) | — | "Keep only one variant per choice group" |
| Missing `resourceType` in output | — | "Use `.model_dump(exclude_none=True)`" |
| Empty result list | — | "Ensure non-empty list" |

---

## FHIR Spec Introspection

At import time, `fhir_spec.py` scans the `fhir.resources.R4B` package and builds:

- **Module map**: `{ClassName: module_name}` for all ~141 resource types
- **Required fields**: detected via both Pydantic `is_required()` and `fhir.resources`' custom `element_required` marker
- **Reference fields**: fields with `ReferenceType` annotation
- **Import guide**: exact `from fhir.resources.R4B.{module} import {Class}` paths

This spec is injected into LLM prompts so the model knows the correct import paths and required fields for every resource type.

---

## Key Design Decisions

### LLM Integration via LiteLLM

All LLM calls go through a thin `LLMProvider` abstraction backed by [LiteLLM](https://docs.litellm.ai/), supporting 100+ providers (OpenAI, Anthropic, AWS Bedrock, Azure, Google Gemini, etc.) with a single interface. AWS Bedrock authentication is handled via `boto3` sessions with support for named profiles, SSO, and environment variables. A `MockLLMProvider` enables testing without API keys.

### Dynamic System Prompt

The system prompt is assembled dynamically from:

- **Sandbox constraints** — built from `ALLOWED_MODULES` in `constants.py`
- **FHIR spec summary** — required/optional/reference fields per resource type
- **Import guide** — introspected `from fhir.resources.R4B.{mod} import {Cls}` paths
- **Reference field map** — exact field names for Patient/Encounter/etc. linkage
- **Chain-of-thought** — step-by-step instructions for code generation

### Custom Metadata

Metadata (security labels, tags, profiles, source) is configured via YAML (`--meta-config`):

```yaml
meta:
  security:
    - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
      code: "N"
      display: "Normal"
  tag:
    - system: "http://example.org/tags"
      code: "synthetic-data"
  source: "http://example.org/fhir-synth"
```

### Executor Backends

All backends are powered by [smolagents](https://huggingface.co/docs/smolagents/tutorials/secure_code_execution). LLM-generated code runs inside a pluggable executor selected via `--executor`:

| Backend | Flag | How it works | Install |
|---|---|---|---|
| **Local (smolagents)** | `--executor local` (default) | Runs code via smolagents' AST-level secure interpreter with import whitelist + restricted builtins | *(built-in)* |
| **Docker** | `--executor docker` | Runs code in an isolated Docker container via smolagents' `DockerExecutor` | `pip install "fhir-synth[docker]"` |
| **E2B** | `--executor e2b` | Runs code in an [E2B](https://e2b.dev) cloud sandbox via smolagents' `E2BExecutor` | `pip install "fhir-synth[e2b]"` |
| **Blaxel** | `--executor blaxel` | Runs code in a [Blaxel](https://blaxel.ai) managed sandbox via smolagents' `BlaxelExecutor` | `pip install "fhir-synth[blaxel]"` |

All backends implement the `Executor` protocol and return a uniform `ExecutionResult(stdout, stderr, artifacts)`. Shared pre-flight validation (import whitelist, dangerous-pattern scan, naive datetime fix) runs before any backend executes.


The E2B API key is resolved in order: `E2B_API_KEY` env var (set it once, works automatically).

### Output Structure

All outputs are auto-saved to `runs/<name>/` with a unique Docker-style name (e.g. `brave_phoenix`):

| Flag | Output |
|---|---|
| *(default)* | `runs/<name>/prompt.txt` + `<name>.py` + `<name>.ndjson` |
| `--split` | Also creates `patient_*.json` in the run directory |
