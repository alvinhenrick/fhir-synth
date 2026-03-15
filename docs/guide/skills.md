# Skills System

FHIR Synth uses a **skills system** to inject domain-specific FHIR knowledge into the LLM context. Skills are modular, self-contained Markdown files following the [agentskills.io](https://agentskills.io/specification) specification.

## Overview

Each skill is a folder containing a `SKILL.md` file with:

- **YAML frontmatter** — Metadata for discovery and selection
- **Markdown body** — Domain-specific guidance for the LLM

Skills are automatically selected based on your prompt and injected into the system context, ensuring the LLM generates realistic, compliant FHIR data.

## Built-in Skills

FHIR Synth includes 13+ production-ready skills covering core healthcare domains:

| Skill | Description | Resource Types |
|-------|-------------|----------------|
| **patient-variation** | Demographics, age distribution, race, ethnicity, language diversity | `Patient` |
| **medications** | RxNorm codes, dosing, timing, adherence patterns | `MedicationRequest` |
| **vitals-and-labs** | LOINC codes, normal ranges, temporal patterns | `Observation` |
| **comorbidity** | Disease clustering, chronic condition patterns | `Condition` |
| **encounters** | Visit types, coding systems, class progression | `Encounter` |
| **coverage** | Insurance diversity (Medicare, Medicaid, commercial) | `Coverage` |
| **allergies-immunizations** | CVX codes, contraindications, vaccine schedules | `AllergyIntolerance`, `Immunization` |
| **careplan-goals** | Care coordination, goal tracking, service requests | `CarePlan`, `Goal`, `ServiceRequest` |
| **diagnostics-documents** | Imaging, reports, diagnostic procedures | `DiagnosticReport`, `DocumentReference` |
| **sdoh** | Social determinants of health (housing, food, employment) | `Observation` |
| **edge-cases** | Missing data, ambiguous records, real-world messiness | All |
| **provenance-data-quality** | Audit trails, data quality flags, source attribution | `Provenance` |
| **family-history** | Genetic conditions, family relationships | `FamilyMemberHistory` |

Skills marked as **always** (patient-variation, edge-cases, provenance-data-quality) are included in every generation.

## Skill Selection

### Keyword Selector (Default)

The **keyword selector** uses fuzzy matching with **typo tolerance** to select relevant skills. It's fast, has zero dependencies, and handles common typos automatically.

**How it works:**

1. Exact keyword matches score **+2 points**
2. Fuzzy matches (≥80% similarity) score **+1 point**
3. Description token overlap scores **+1 point per token**
4. Skills scoring ≥1 are selected
5. Safe fallback: if nothing matches, all skills are included

**Examples:**

```bash
# Exact match
fhir-synth generate "10 patients with diabetes and medications"
# → Selects: medications, comorbidity

# Typo tolerance
fhir-synth generate "10 patients with diabtes and medicaton"
# → Still selects: medications, comorbidity
# "diabtes" → "diabetes" ✓ (88% similarity)
# "medicaton" → "medication" ✓ (91% similarity)

# Resource type matching
fhir-synth generate "Generate 20 Observation resources"
# → Selects: vitals-and-labs, sdoh
```

**Configuration:**

The keyword selector uses a fuzzy threshold of 0.8 (80% similarity) by default. This is tuned to catch common typos while avoiding false matches.

### FAISS Selector (Optional)

The **FAISS selector** uses semantic embeddings for similarity-based retrieval. It's best for large custom skill sets or when you need semantic understanding beyond keywords.

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

# Adjust similarity threshold (0.0-1.0)
fhir-synth generate "5 patients" --selector faiss --score-threshold 0.5
```

**How it works:**

1. On first run: embeds all skills → builds FAISS index → saves to `~/.cache/fhir-synth/skills/`
2. Subsequent runs: loads cached index (instant)
3. Embeds your prompt → searches for similar skills
4. Returns all skills above similarity threshold (default: 0.3)

**When to use FAISS:**

- You have 50+ custom skills
- You need semantic matching ("blood sugar" ≈ "glucose", "HTN" ≈ "hypertension")
- You're building a specialized domain (oncology, genomics, etc.)

**When to use keyword (default):**

- You have ≤20 skills (built-in skills work great)
- You want zero extra dependencies
- Keyword + typo tolerance is sufficient

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
description: Generate cancer conditions with TNM staging observations and treatment plans
keywords: [cancer, oncology, staging, tnm, tumor, node, metastasis, chemotherapy]
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
|-------|----------|------|-------------|
| `name` | ✓ | string | Unique identifier (lowercase, hyphens, max 64 chars) |
| `description` | ✓ | string | What the skill does and when to use it (max 1024 chars) |
| `keywords` | | list | Trigger words for keyword matching |
| `resource_types` | | list | FHIR resource types this skill covers |
| `always` | | boolean | Include in every generation (default: false) |

### Using Custom Skills

```bash
# Use custom skills directory
fhir-synth generate "5 lung cancer patients" --skills-dir ~/.fhir-synth/skills

# Custom skills override built-in skills with the same name
# Priority: user skills > built-in skills
```

## Best Practices

### Writing Effective Skills

1. **Be specific**: Include exact code systems, value sets, and LOINC/SNOMED/RxNorm codes
2. **Provide examples**: Show realistic data patterns
3. **Explain temporal relationships**: When do observations occur relative to encounters?
4. **Note edge cases**: Missing data, unusual values, contraindications
5. **Keep it focused**: One skill per clinical domain

### Keyword Selection Tips

Choose keywords that users would naturally type:

```yaml
# Good keywords — match user intent
keywords: [diabetes, diabetic, glucose, hba1c, insulin, blood sugar, a1c]

# Avoid overly broad keywords that trigger on everything
keywords: [patient, observation, condition]  # ❌ Too broad
```

### When to Mark `always: true`

Use `always: true` sparingly. Reserve it for:

- **Foundational skills** everyone needs (patient demographics)
- **Data quality guidelines** that apply to all generations
- **Compliance requirements** (provenance, audit trails)

Most skills should be `always: false` and selected based on the prompt.

## Troubleshooting

### Skills Not Being Selected

If your prompt doesn't match any skills:

1. Check your keywords for typos (fuzzy matching helps, but isn't perfect)
2. Verify `resource_types` match what you're requesting
3. Try more specific keywords in your prompt
4. As a fallback, all skills are included when nothing matches

### FAISS Import Errors

If you see `ImportError: No module named 'faiss'`:

```bash
pip install fhir-synth[semantic]
```

### Viewing Selected Skills

Enable debug logging to see which skills were selected:

```bash
export LOG_LEVEL=DEBUG
fhir-synth generate "10 patients with diabetes"
```

Look for:
```
INFO Selected 3/13 skills: medications, comorbidity, vitals-and-labs
```

## API Usage

Use skills programmatically in Python:

```python
from pathlib import Path
from fhir_synth.skills import SkillLoader, KeywordSelector, FaissSelector

# Discover skills
loader = SkillLoader(user_dirs=[Path("~/.fhir-synth/skills")])
all_skills = loader.discover()

# Select with keyword matcher
selector = KeywordSelector(min_score=1, fuzzy_threshold=0.8)
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
