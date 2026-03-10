# Metadata Configuration

Add security labels, tags, profiles, and other FHIR metadata to generated resources.

## YAML Configuration

Create a metadata YAML file and pass it to the `generate` command:

```yaml
# meta-normal.yaml
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

```bash
fhir-synth generate "20 patients with conditions" --meta-config examples/meta-normal.yaml -o output.json
```

## Supported Fields

| YAML Key | Description |
|----------|-------------|
| `security` | Security labels (confidentiality, sensitivity) — list of `{system, code, display}` |
| `tag` | Tags for operational/workflow purposes — list of `{system, code, display}` |
| `profile` | Profile URLs the resource conforms to — list of URL strings |
| `source` | Source system URI — string |

## Restricted Data Example

```yaml
# meta-restricted.yaml
meta:
  security:
    - system: "http://terminology.hl7.org/CodeSystem/v3-Confidentiality"
      code: "R"
      display: "Restricted"
    - system: "http://terminology.hl7.org/CodeSystem/v3-ActCode"
      code: "ETH"
      display: "Substance Abuse Related"
  tag:
    - system: "http://example.org/tags"
      code: "restricted-synthetic"
      display: "Restricted Synthetic Data"
  profile:
    - "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"
  source: "http://example.org/fhir-synth/restricted"
```

## Programmatic Metadata

You can also apply metadata programmatically using the `CodeGenerator.apply_metadata_to_resources()` static method:

```python
from fhir_synth.code_generator import CodeGenerator

# Generate resources
resources = code_gen.execute_generated_code(code)

# Apply metadata
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

