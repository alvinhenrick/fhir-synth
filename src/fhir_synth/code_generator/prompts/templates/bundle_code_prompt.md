Generate Python code that creates FHIR R4B resources and returns them as a flat list.

Requirements:
- Resource types to generate: $resources_str
- Count per type: $count_per_resource
- Link clinical resources to Patients (subject references)
- Link Encounters to Patients and Practitioners
- Use real clinical codes (ICD-10, LOINC, RxNorm, SNOMED)
- def generate_resources() -> list[dict]:
- .model_dump(exclude_none=True) on every resource
- uuid4 for IDs, Decimal for numeric values
- Ensure patient demographic diversity (age, gender, race, ethnicity, language)
- Use realistic comorbidity clusters (not random independent conditions)
- Include vital signs with components, lab results with reference ranges
- Vary data completeness across patients (some sparse, some comprehensive)
- Include Coverage/insurance when generating patient-centric bundles

$fhir_imports

FHIR SPEC (required, reference, and optional fields):
$fhir_spec

