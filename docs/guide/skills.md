# Skills System

FHIR Synth uses a **skills system** to inject domain-specific FHIR knowledge into the LLM context. Skills are modular, self-contained Markdown files following the [agentskills.io](https://agentskills.io/specification) specification.

## Overview

Each skill is a folder containing a `SKILL.md` file with:

- **YAML frontmatter** — Metadata for discovery and selection
- **Markdown body** — Domain-specific guidance for the LLM

Per the agentskills.io spec, **`description` is the selection signal** — selectors tokenize or embed it to decide when the skill applies. FHIR Synth adds one extension field, `resource_types`, that gives the selector a precise structural signal when the user names a FHIR resource type directly.

Skills are automatically selected based on your prompt and injected into the system context, ensuring the LLM generates realistic, compliant FHIR data.

## Built-in Skills

FHIR Synth ships 17 production-ready skills covering core healthcare domains:

| Skill | Description | Resource Types |
| --- | --- | --- |
| **patient-variation** | Demographics, age distribution, race, ethnicity, language diversity | `Patient` |
| **medications** | Full medication family — RxNorm, dosing, dispensing, administration, statements | `Medication`, `MedicationRequest`, `MedicationDispense`, `MedicationAdministration`, `MedicationStatement`, `MedicationKnowledge` |
| **vitals-and-labs** | LOINC codes, normal ranges, temporal patterns | `Observation` |
| **comorbidity** | Disease clustering, chronic condition patterns | `Condition` |
| **encounters** | Visit types, coding systems, class progression | `Encounter` |
| **coverage** | Insurance diversity (Medicare, Medicaid, commercial) | `Coverage` |
| **allergies-immunizations** | CVX codes, contraindications, vaccine schedules | `AllergyIntolerance`, `Immunization` |
| **careplan-goals** | Care coordination, goal tracking, service requests | `CarePlan`, `Goal`, `ServiceRequest` |
| **care-team** | Care team composition and roles | `CareTeam`, `Practitioner`, `PractitionerRole`, `Organization`, `Location` |
| **diagnostics-documents** | Imaging, reports, diagnostic procedures | `DiagnosticReport`, `DocumentReference` |
| **procedures** | Surgical and non-surgical procedures | `Procedure` |
| **claims-eob** | Claims and explanation of benefits | `Claim`, `ExplanationOfBenefit` |
| **sdoh** | Social determinants of health (housing, food, employment) | `Observation` |
| **longitudinal** | Multi-encounter timelines, disease progression, treatment response | All |
| **edge-cases** | Missing data, ambiguous records, real-world messiness | All |
| **provenance-data-quality** | Audit trails, data quality flags, source attribution | `Provenance` |
| **family-history** | Genetic conditions, family relationships | `FamilyMemberHistory` |

Skills marked **`always: true`** in their frontmatter (patient-variation, edge-cases, provenance-data-quality) are included in every generation.

## Skill Selection

### Keyword Selector (Default)

The default selector scores skills by **token overlap between the prompt and the skill's `description` + `name`**, with a fuzzy fallback for typo tolerance via Python's built-in `difflib`. Zero dependencies.

**How it works:**

1. Resource-type substring hit (e.g. user wrote "MedicationRequest") → **+2 points**
2. Token overlap between prompt and skill description/name → **+1 per shared token**
3. Fuzzy fallback (≥85% similarity) when score is still 0 → **+1 point**
4. Skills scoring ≥ `min_score` (default 1) are selected
5. **Safe fallback**: if nothing matches, all skills are included

**Examples:**

```bash
# Description-token match
fhir-synth generate "10 patients with diabetes and medications"
# → Selects: medications (description names "medication"), comorbidity ("diabetes")

# Typo tolerance via fuzzy fallback
fhir-synth generate "10 patients with diabtes and medicaton"
# → Still selects: medications, comorbidity

# Resource-type matching
fhir-synth generate "Generate 20 Observation resources"
# → Selects: vitals-and-labs, sdoh (both list Observation)
```

**Configuration:**

The default fuzzy threshold is 0.85 (85% similarity). Tune via `KeywordSelector(fuzzy_threshold=0.8)` for more tolerant matching.

### FAISS Selector (Optional)

The **FAISS selector** uses semantic embeddings of the skill description for similarity-based retrieval. Best for large custom skill sets or when you need semantic understanding ("blood sugar" ≈ "glucose").

**Installation:**

```bash
pip install fhir-synth[semantic]
```

This installs:

- `faiss-cpu` — Vector similarity search
- `sentence-transformers` — Local embedding model (all-MiniLM-L6-v2, 384-dim, ~80MB)
- `numpy` — Array operations

**Usage:**

```bash
# Basic usage
fhir-synth generate "5 patients" --selector faiss

# Adjust similarity threshold (0.0–1.0)
fhir-synth generate "5 patients" --selector faiss --score-threshold 0.5
```

**How it works:**

1. On first run: embeds all skill descriptions → builds FAISS index → saves to `~/.cache/fhir-synth/skills/`
2. Subsequent runs: loads cached index (instant)
3. Embeds your prompt → searches for similar skills
4. Returns all skills above the similarity threshold (default 0.3)

**When to use FAISS:**

- You have 50+ custom skills
- You need semantic matching ("HTN" ≈ "hypertension")
- You're building a specialized domain (oncology, genomics, etc.)

**When to use keyword (default):**

- You have ≤20 skills (built-in skills work great)
- You want zero extra dependencies
- Token overlap + typo tolerance is sufficient

## Custom Skills

Create your own skills to extend FHIR Synth with domain-specific knowledge.

### Skill Structure

Each skill is a directory with a `SKILL.md` file:

```
~/.fhir-synth/skills/
├── oncology-staging/
│   └── SKILL.md
└── genomics/
    └── SKILL.md
```

### SKILL.md Format

```yaml
---
name: oncology-staging
description: Generate cancer conditions with TNM staging observations and treatment plans. Use when user mentions cancer, oncology, tumor, staging, TNM, metastasis, chemotherapy, or radiation.
resource_types: [Condition, Observation, MedicationRequest, Procedure]
always: false
---

# Oncology Staging

Generate cancer patients with realistic staging and treatment data.

## Primary Cancer Conditions

Use SNOMED CT codes for cancer diagnoses:
- 93655004 — Primary malignant neoplasm of lung
- 254837009 — Malignant neoplasm of breast
- 363418001 — Malignant neoplasm of colon

## TNM Staging

Create TNM staging observations using LOINC 21908-9 (Stage group):
- Use components for T (tumor), N (node), M (metastasis)
- Example: T2N1M0 = Stage IIB

## Treatment Plans

Include appropriate treatments:
- Chemotherapy: `MedicationRequest` with RxNorm codes
- Radiation: `Procedure` with SNOMED codes
- Surgery: `Procedure` with ICD-10-PCS codes
```

### Frontmatter Fields

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `name` | ✓ | string | Unique identifier (lowercase, hyphens, max 64 chars) |
| `description` | ✓ | string | What the skill does and when to use it. **This is the selection signal** — bake your trigger terms (conditions, drugs, code systems, resource type names) into the natural-language description. Max 1024 chars. |
| `resource_types` |   | list | FHIR resource types this skill covers — gives the selector a precise structural signal when the user names a FHIR type directly |
| `always` |   | boolean | Include in every generation (default: false) |

!!! note "Migrating from older skills with `keywords:`"
    Earlier versions of fhir-synth used a separate `keywords:` field for matching. That field is now a deviation from the agentskills.io spec and has been removed — the loader silently ignores any legacy `keywords:` you leave in place, so old skills keep working. To get the same matching power, **fold your keywords into the description as natural language** (see the "Use when user mentions …" pattern used by every built-in skill).

### Using Custom Skills

```bash
# Use a custom skills directory
fhir-synth generate "5 lung cancer patients" --skills-dir ~/.fhir-synth/skills

# Custom skills override built-in skills with the same name
# Priority: user skills > built-in skills
```

## Best Practices

### Writing Effective Skills

1. **Front-load triggers in `description`.** The first 1–2 sentences should name the conditions, drugs, code systems, and resource types a user might mention. The selector sees this verbatim.
2. **Use the "Use when user mentions …" pattern.** Built-in descriptions end with that clause — it concentrates trigger terms where both the keyword and FAISS selectors will pick them up.
3. **Be specific in the body.** Include exact LOINC / SNOMED / RxNorm codes, value sets, units, status enums.
4. **Provide examples.** Show realistic data patterns and resource cross-references.
5. **Note edge cases.** Missing data, unusual values, contraindications.
6. **Keep skills focused.** One skill per clinical domain.

### When to Mark `always: true`

Use `always: true` sparingly. Reserve it for:

- **Foundational skills** everyone needs (patient demographics)
- **Data-quality guidelines** that apply to every generation
- **Compliance requirements** (provenance, audit trails)

Most skills should be `always: false` and selected based on the prompt.

## Troubleshooting

### Skills Not Being Selected

If your prompt doesn't match any skills:

1. Check that trigger terms (drug names, conditions, resource types) appear in the skill's `description` — not just the body.
2. Verify `resource_types` matches what the prompt asks for (e.g. include `Observation` if users ask for "labs").
3. Try more specific terms in your prompt, or lower the keyword selector's `fuzzy_threshold` (default 0.85).
4. As a safe fallback, all skills are included when nothing matches.

### FAISS Import Errors

```bash
pip install fhir-synth[semantic]
```

### Viewing Selected Skills

```bash
export LOG_LEVEL=DEBUG
fhir-synth generate "10 patients with diabetes"
```

Look for:

```
INFO Selected 3/17 skills: medications, comorbidity, vitals-and-labs
```

## API Usage

```python
from pathlib import Path
from fhir_synth.skills import SkillLoader, KeywordSelector, FaissSelector

# Discover skills
loader = SkillLoader(user_dirs=[Path("~/.fhir-synth/skills")])
all_skills = loader.discover()

# Select with keyword matcher (default)
selector = KeywordSelector(min_score=1, fuzzy_threshold=0.85)
selected = selector.select("10 diabetic patients with labs", all_skills)

# Select with FAISS
faiss_selector = FaissSelector(score_threshold=0.3)
selected = faiss_selector.select("10 diabetic patients with labs", all_skills)

# Get skill bodies for LLM context
skill_context = "\n\n".join(s.body for s in selected)
```

## Next Steps

- Browse [built-in skills source](https://github.com/alvinhenrick/fhir-synth/tree/main/src/fhir_synth/skills/builtin)
- Explore the [agentskills.io specification](https://agentskills.io/specification)
- Check out [CLI Reference](cli.md) for all skill-related flags
- Learn about [LLM Providers](providers.md) that work best with skills
