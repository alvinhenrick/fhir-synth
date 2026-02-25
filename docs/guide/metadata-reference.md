# Metadata Quick Reference

## YAML Config File

Create a reusable YAML config file and use it with `--meta-config`:

**meta-normal.yaml:**
```yaml
meta:
  security:
    - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
      code: "N"
      display: "Normal"
  tag:
    - system: "http://example.org/tags"
      code: "synthetic-data"
      display: "Synthetic Test Data"
  profile:
    - "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
  source: "http://example.org/fhir-synth"
```

**Usage:**
```bash
fhir-synth generate "10 diabetic patients" --meta-config examples/meta-normal.yaml -o output.json
```

!!! tip "LLM-Powered Metadata"
    You can also describe metadata in your prompt — the LLM understands requests like
    "10 HIV patients with restricted security labels" and generates code with `Meta` and `Coding` models.

---

## Common Metadata Patterns

### Security Labels (Confidentiality)

```yaml
# Normal confidentiality
security:
  - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
    code: "N"
    display: "Normal"

# Restricted access
security:
  - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
    code: "R"
    display: "Restricted"

# Very restricted (sensitive)
security:
  - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
    code: "V"
    display: "Very restricted"
```

### Tags (Classification)

```yaml
# Synthetic data tag
tag:
  - system: "http://example.org/tags"
    code: "synthetic-data"
    display: "Synthetic Test Data"

# Study enrollment tag
tag:
  - system: "http://example.org/study"
    code: "STUDY-2026-001"
    display: "Clinical Study 2026-001"

# Data classification tag
tag:
  - system: "http://example.org/data-classification"
    code: "test-only"
    display: "Test Data Only"
```

### Profiles (Conformance)

```yaml
# US Core Patient
profile:
  - "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"

# US Core Condition
profile:
  - "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition"

# US Core Observation
profile:
  - "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation"

# Multiple profiles
profile:
  - "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
  - "http://example.org/fhir/StructureDefinition/research-patient"
```

### Source System

```yaml
# EHR system
source: "http://hospital-ehr.example.org/fhir"

# Lab system
source: "http://lab-system.example.org/fhir"

# Research database
source: "http://research-db.example.org/fhir"
```

### Version Tracking

```yaml
# Version and timestamp
versionId: "v2.1"
lastUpdated: "2026-02-23T12:00:00Z"
```

## Example Metadata Configs

### examples/meta-normal.yaml (Normal Confidentiality)
```yaml
meta:
  security:
    - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
      code: "N"
      display: "Normal"
  tag:
    - system: "http://example.org/tags"
      code: "synthetic-data"
      display: "Synthetic Test Data"
  profile:
    - "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
  source: "http://example.org/fhir-synth"
```

**Usage:**
```bash
fhir-synth generate "20 patients with diabetes" --meta-config examples/meta-normal.yaml -o output.json
```

### examples/meta-restricted.yaml (Sensitive Data)
```yaml
meta:
  security:
    - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
      code: "R"
      display: "Restricted"
    - system: "http://terminology.hl7.org/CodeSystem/v3-ActCode"
      code: "HIV"
      display: "HIV/AIDS Information"
  tag:
    - system: "http://example.org/data-classification"
      code: "sensitive"
      display: "Sensitive Information"
  profile:
    - "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition"
  source: "http://hospital-ehr.example.org/fhir"
```

**Usage:**
```bash
fhir-synth generate "10 HIV patients" --meta-config examples/meta-restricted.yaml -o hiv.json
```

## Output Example

```json
{
  "resourceType": "Patient",
  "id": "abc-123",
  "name": [{"family": "Smith", "given": ["John"]}],
  "meta": {
    "security": [
      {
        "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
        "code": "N",
        "display": "Normal"
      }
    ],
    "tag": [
      {
        "system": "http://example.org/study",
        "code": "DIABETES-2026",
        "display": "Diabetes Study 2026"
      }
    ],
    "profile": [
      "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
    ],
    "source": "http://hospital.example.org/fhir"
  }
}
```

## More Examples

See:
- `examples/meta-normal.yaml` — Normal confidentiality config
- `examples/meta-restricted.yaml` — Restricted security for sensitive data

