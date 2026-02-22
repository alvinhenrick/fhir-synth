"""Dynamic code generation for FHIR resources from LLM prompts."""

from typing import Any

from fhir_synth.fhir_spec import resource_names
from fhir_synth.llm import LLMProvider

# Auto-discovered from fhir.resources — covers ALL R4B resource types (~141)
SUPPORTED_RESOURCE_TYPES: list[str] = resource_names()


class CodeGenerator:
    """Generates Python code for FHIR resource creation from natural language."""

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

    def __init__(self, llm: LLMProvider, max_retries: int = 2) -> None:
        """Initialize code generator with LLM.

        Args:
            llm: LLM provider for code generation
            max_retries: Number of times to retry if generated code fails execution
        """
        self.llm = llm
        self.max_retries = max_retries

    def generate_code_from_prompt(self, prompt: str) -> str:
        """Generate Python code from natural language prompt.

        Args:
            prompt: Natural language description of resources to generate

        Returns:
            Generated Python code as string
        """
        user_prompt = f"""Generate Python code to create FHIR R4B resources.

Requirement: {prompt}

Remember:
- def generate_resources() -> list[dict]:
- import from fhir.resources.R4B (e.g. from fhir.resources.R4B.patient import Patient)
- .model_dump(exclude_none=True) on every resource
- uuid4 for IDs, Decimal for numeric values
- real clinical codes (ICD-10, LOINC, RxNorm, SNOMED)
- diverse, realistic data"""

        code = self.llm.generate_text(self.SYSTEM_PROMPT, user_prompt)
        return self._extract_code(code)

    def generate_rules_from_prompt(self, prompt: str) -> dict[str, Any]:
        """Generate rule definitions from prompt.

        Args:
            prompt: Natural language description of generation rules

        Returns:
            Dictionary of rule definitions
        """
        user_prompt = f"""Convert this natural language requirement into structured generation rules:

{prompt}

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
        result = self.llm.generate_json(self.SYSTEM_PROMPT, user_prompt)
        return result

    def generate_bundle_code(self, resource_types: list[str], count_per_resource: int = 10) -> str:
        """Generate code for creating a FHIR bundle with multiple resource types.

        Args:
            resource_types: List of FHIR resource types to include (e.g., ["Patient", "Condition"])
            count_per_resource: Number of each resource type to generate

        Returns:
            Generated Python code
        """
        resources_str = ", ".join(resource_types)
        user_prompt = f"""Generate Python code that creates FHIR R4B resources and returns them as a flat list.

Requirements:
- Resource types to generate: {resources_str}
- Count per type: {count_per_resource}
- Link clinical resources to Patients (subject references)
- Link Encounters to Patients and Practitioners
- Use real clinical codes (ICD-10, LOINC, RxNorm, SNOMED)
- def generate_resources() -> list[dict]:
- .model_dump(exclude_none=True) on every resource
- uuid4 for IDs, Decimal for numeric values"""

        code = self.llm.generate_text(self.SYSTEM_PROMPT, user_prompt)
        return self._extract_code(code)

    def validate_code(self, code: str) -> bool:
        """Validate that generated code is safe and syntactically correct.

        Args:
            code: Python code to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            compile(code, "<generated>", "exec")
            return True
        except SyntaxError:
            return False

    def execute_generated_code(self, code: str, timeout: int = 30) -> list[dict[str, Any]]:
        """Execute generated code safely, with self-healing retry on failure.

        If execution fails, the error is sent back to the LLM to produce a
        corrected version. This repeats up to ``max_retries`` times.

        Args:
            code: Generated Python code
            timeout: Timeout in seconds

        Returns:
            List of generated resources
        """
        last_error: Exception | None = None

        for attempt in range(1 + self.max_retries):
            if not self.validate_code(code):
                last_error = ValueError("Generated code is not valid Python")
                code = self._retry_with_error(code, str(last_error))
                continue

            try:
                return self._exec_code(code)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_retries:
                    code = self._retry_with_error(code, str(exc))

        raise RuntimeError(
            f"Code execution failed after {self.max_retries + 1} attempts: {last_error}"
        ) from last_error

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _exec_code(self, code: str) -> list[dict[str, Any]]:
        """Run ``code`` in a sandboxed namespace and return resources."""
        safe_globals: dict[str, Any] = {
            "__builtins__": {
                "dict": dict,
                "list": list,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "isinstance": isinstance,
                "print": print,
                "__import__": __import__,
            }
        }

        exec(code, safe_globals)  # noqa: S102

        if "generate_resources" in safe_globals:
            result = safe_globals["generate_resources"]()
            return result if isinstance(result, list) else [result]

        raise ValueError("Generated code must define generate_resources() function")

    def _retry_with_error(self, code: str, error: str) -> str:
        """Ask the LLM to fix broken generated code.

        Args:
            code: The code that failed
            error: The error message / traceback

        Returns:
            Corrected Python code
        """
        fix_prompt = f"""The following Python code failed with this error:

ERROR:
{error}

CODE:
{code}

Fix the code so it runs without errors. Keep the same function signature:
  def generate_resources() -> list[dict]:
Return ONLY the corrected Python code, no explanation."""

        fixed = self.llm.generate_text(self.SYSTEM_PROMPT, fix_prompt)
        return self._extract_code(fixed)

    @staticmethod
    def _extract_code(response: str) -> str:
        """Extract Python code from LLM response.

        Handles Markdown code blocks and plain text responses.

        Args:
            response: LLM response text

        Returns:
            Extracted Python code
        """
        # Try to extract from markdown code block
        if "```python" in response:
            start = response.find("```python") + 9
            end = response.find("```", start)
            if end > start:
                return response[start:end].strip()

        if "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                code = response[start:end].strip()
                # Remove language specifier if present
                lines = code.split("\n")
                if (
                    lines[0]
                    and not lines[0].startswith("def ")
                    and not lines[0].startswith("import")
                ):
                    code = "\n".join(lines[1:])
                return code

        return response.strip()


class PromptToRulesConverter:
    """Convert natural language prompts to declarative rules."""

    def __init__(self, llm: LLMProvider) -> None:
        """Initialize converter."""
        self.llm = llm
        self.code_gen = CodeGenerator(llm)

    def convert_prompt_to_rules(self, prompt: str) -> dict[str, Any]:
        """Convert a prompt to generation rules.

        Args:
            prompt: User prompt describing data to generate

        Returns:
            Dictionary of rules
        """
        return self.code_gen.generate_rules_from_prompt(prompt)

    def convert_prompt_to_code(self, prompt: str) -> str:
        """Convert a prompt to executable Python code.

        Args:
            prompt: User prompt describing data to generate

        Returns:
            Generated Python code
        """
        return self.code_gen.generate_code_from_prompt(prompt)

    def extract_resource_types(self, prompt: str) -> list[str]:
        """Extract FHIR resource types mentioned in prompt.

        Args:
            prompt: User prompt

        Returns:
            List of resource types
        """
        prompt_lower = prompt.lower()
        found = [rt for rt in SUPPORTED_RESOURCE_TYPES if rt.lower() in prompt_lower]

        # Default to Patient if none found
        return found or ["Patient"]
