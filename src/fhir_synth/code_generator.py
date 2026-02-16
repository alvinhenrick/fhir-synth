"""Dynamic code generation for FHIR resources from LLM prompts."""

from typing import Any

from fhir_synth.llm import LLMProvider


class CodeGenerator:
    """Generates Python code for FHIR resource creation from natural language."""

    SYSTEM_PROMPT = """You are an expert FHIR R4 resource generator. Convert natural language 
descriptions into Python code that generates FHIR resources using the fhir.resources library.

Guidelines:
1. Use fhir.resources library (Patient, Condition, Observation, etc.)
2. Generate realistic, diverse, and valid FHIR R4 data
3. Return clean, executable Python code
4. Always import from fhir.resources: from fhir.resources import [ResourceType]
5. Create a function: def generate_resources() -> list[dict]:
6. Use proper FHIR data types and structures
7. Return list of resource dictionaries (use .model_dump() on Pydantic models)
8. Include realistic IDs, dates, and relationships between resources
9. Add docstring explaining what the code generates
10. Ensure all FHIR required fields are present (id, resourceType, status where required)"""

    def __init__(self, llm: LLMProvider) -> None:
        """Initialize code generator with LLM."""
        self.llm = llm

    def generate_code_from_prompt(self, prompt: str) -> str:
        """Generate Python code from natural language prompt.

        Args:
            prompt: Natural language description of resources to generate

        Returns:
            Generated Python code as string
        """
        user_prompt = f"""Generate Python code to create FHIR R4 resources using fhir.resources library.

Requirement: {prompt}

Code requirements:
- Use fhir.resources library (from fhir.resources import Patient, Condition, etc.)
- Generate realistic, diverse data
- Function signature: def generate_resources() -> list[dict]:
- Return list of dictionaries (call .model_dump() on Pydantic models)
- Ensure all required FHIR fields are included
- Use proper FHIR data types and coding systems
- Add meaningful comments explaining the generation logic"""

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

    def generate_bundle_code(
            self, resource_types: list[str], count_per_resource: int = 10
    ) -> str:
        """Generate code for creating a FHIR bundle with multiple resource types.

        Args:
            resource_types: List of FHIR resource types to include (e.g., ["Patient", "Condition"])
            count_per_resource: Number of each resource type to generate

        Returns:
            Generated Python code
        """
        resources_str = ", ".join(resource_types)
        user_prompt = f"""Generate Python code that creates a FHIR R4 Bundle using fhir.resources library.

Requirements:
- Resource types: {resources_str}
- Count per type: {count_per_resource}
- Create realistic relationships (e.g., Conditions reference Patients)
- Use fhir.resources library classes
- Return complete Bundle as dictionary

Code must:
1. Import from fhir.resources: from fhir.resources import Bundle, {resources_str}
2. Define function: def generate_bundle() -> dict:
3. Create {count_per_resource} of each resource type
4. Link clinical resources to patients (Condition.subject, Observation.subject, etc.)
5. Return Bundle.model_dump() as the result
6. Ensure all IDs are unique and valid"""

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
        """Execute generated code safely.

        Args:
            code: Generated Python code
            timeout: Timeout in seconds

        Returns:
            List of generated resources
        """
        if not self.validate_code(code):
            raise ValueError("Generated code is not valid Python")

        # Create safe execution environment
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
                "__import__": __import__,
            }
        }

        try:
            exec(code, safe_globals)
            if "generate_resources" in safe_globals:
                func = safe_globals["generate_resources"]
                result = func()
                return result if isinstance(result, list) else [result]
            else:
                raise ValueError("Generated code must define generate_resources() function")
        except Exception as e:
            raise RuntimeError(f"Error executing generated code: {e}") from e

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
                if lines[0] and not lines[0].startswith("def ") and not lines[0].startswith("import"):
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
        # Try to identify from prompt
        resource_types = [
            "Person"
            "Patient",
            "Condition",
            "Medication",
            "MedicationRequest",
            "MedicationDispense",
            "Observation",
            "Procedure",
            "Encounter",
            "Organization",
            "Location",
            "Practitioner",
            "PractitionerRole"
            "DiagnosticReport",
            "DocumentReference",
        ]

        found = []
        for rt in resource_types:
            if rt.lower() in prompt.lower():
                found.append(rt)

        # Default to Patient if none found
        return found or ["Patient"]
