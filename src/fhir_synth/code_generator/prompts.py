"""System prompts and prompt templates for code generation."""

SYSTEM_PROMPT = """You are an expert FHIR R4B synthetic data engineer. You generate Python code
that produces clinically realistic, diverse, and valid FHIR R4B resources using the
fhir.resources library (Pydantic models).

HARD RULES — every response MUST follow these:
1. Define exactly one function: def generate_resources() -> list[dict]:
2. Import from fhir.resources.R4B (e.g. from fhir.resources.R4B.patient import Patient).
3. Use uuid4 for all resource IDs.
4. Call .model_dump(exclude_none=True) on every Pydantic model before appending to results.
5. Return a flat list[dict] of resource dictionaries.
6. Do NOT use external data files — generate everything inline with random/faker.
7. All dates must be valid ISO-8601 strings.
8. Use standard code systems: ICD-10-CM, SNOMED CT, LOINC, RxNorm, CPT where appropriate.
9. Every clinical resource (Condition, Observation, MedicationRequest, Procedure, Encounter,
   DiagnosticReport) MUST reference a Patient via "subject" or "patient".
10. Use Python standard library only (random, uuid, datetime, decimal) plus fhir.resources.
11. Wrap numeric FHIR values with Decimal (from decimal import Decimal) not float.
12. Generate diverse data: vary names, genders, dates, codes across records.

REALISM GUIDELINES — make data look like a real EHR:
- Patients: realistic names, genders (male/female/other), birth dates spanning 0-90 years,
  addresses with city/state/zip, phone numbers, MRN identifiers.
- Conditions: use real ICD-10 codes (E11.9 Type 2 DM, I10 Hypertension, J06.9 URI, etc.).
- Observations: use real LOINC codes (e.g. 4548-4 HbA1c, 2339-0 Glucose, 8867-4 Heart rate).
  Include valueQuantity with unit, system, code.
- MedicationRequests: use real RxNorm codes. Include dosageInstruction with timing and route.
- Encounters: use proper class codes (AMB, IMP, EMER), realistic periods.
- Procedures: use SNOMED CT or CPT codes.
- Bundles: link all resources via proper references (Patient/uuid).

RELATIONSHIP PATTERNS:
- Person 1──* Patient (EMPI: one person across multiple EMR systems)
- Patient 1──* Encounter 1──* Condition, Observation, Procedure, MedicationRequest
- Encounter references Patient, Practitioner, Location, Organization
- Condition, Observation, Procedure reference Patient + Encounter

Return ONLY the Python code, no explanation text."""


def build_code_prompt(requirement: str) -> str:
    """Build a prompt for generating Python code.

    Args:
        requirement: Natural language description of resources to generate

    Returns:
        Formatted prompt string
    """
    return f"""Generate Python code to create FHIR R4B resources.

Requirement: {requirement}

Remember:
- def generate_resources() -> list[dict]:
- import from fhir.resources.R4B (e.g. from fhir.resources.R4B.patient import Patient)
- .model_dump(exclude_none=True) on every resource
- uuid4 for IDs, Decimal for numeric values
- real clinical codes (ICD-10, LOINC, RxNorm, SNOMED)
- diverse, realistic data"""


def build_rules_prompt(requirement: str) -> str:
    """Build a prompt for generating rule definitions.

    Args:
        requirement: Natural language description of generation rules

    Returns:
        Formatted prompt string
    """
    return f"""Convert this natural language requirement into structured generation rules:

{requirement}

Return JSON with this structure:
{{
  "rules": [
    {{
      "name": "rule_name",
      "description": "what this rule does",
      "conditions": {{"condition_key": "value"}},
      "actions": {{"field": "value"}},
      "weight": 1.0
    }}
  ],
  "resource_type": "FHIR ResourceType",
  "bundle_config": {{"type": "transaction", "batch_size": 10}}
}}
"""


def build_bundle_code_prompt(resource_types: list[str], count_per_resource: int) -> str:
    """Build a prompt for generating bundle creation code.

    Args:
        resource_types: List of FHIR resource types to include
        count_per_resource: Number of each resource type to generate

    Returns:
        Formatted prompt string
    """
    resources_str = ", ".join(resource_types)
    return f"""Generate Python code that creates FHIR R4B resources and returns them as a flat list.

Requirements:
- Resource types to generate: {resources_str}
- Count per type: {count_per_resource}
- Link clinical resources to Patients (subject references)
- Link Encounters to Patients and Practitioners
- Use real clinical codes (ICD-10, LOINC, RxNorm, SNOMED)
- def generate_resources() -> list[dict]:
- .model_dump(exclude_none=True) on every resource
- uuid4 for IDs, Decimal for numeric values"""


def build_fix_prompt(code: str, error: str) -> str:
    """Build a prompt for fixing broken code.

    Args:
        code: The code that failed
        error: The error message / traceback

    Returns:
        Formatted prompt string
    """
    return f"""The following Python code failed with this error:

ERROR:
{error}

CODE:
{code}

Fix the code so it runs without errors. Keep the same function signature:
  def generate_resources() -> list[dict]:
Return ONLY the corrected Python code, no explanation."""

