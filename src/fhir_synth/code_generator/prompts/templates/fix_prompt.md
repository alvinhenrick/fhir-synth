The following Python code failed with this error:

ERROR:
$error

CODE:
$code

$fhir_imports

SANDBOX CONSTRAINTS — only these imports are allowed:
- Modules: $allowed_list, $allowed_prefixes
- FORBIDDEN builtins: eval(), exec(), open(), compile(), globals(), __import__()

Read the error carefully and fix the code:
- If "Import of X is not allowed", replace with an allowed alternative.
- If "missing 'resourceType'", call .model_dump(exclude_none=True) on Pydantic models.
- If "returned empty list", ensure generate_resources() returns a non-empty list.
- If it is a Pydantic ValidationError, the error tells you exactly which field on which
  resource type is invalid and why. Fix that field value so it passes model_validate().
  The FHIR SPEC and IMPORT GUIDE provided above have the correct types and constraints.

Fix the code so it runs without errors. Keep the same function signature:
  def generate_resources() -> list[dict]:
Return ONLY the corrected Python code, no explanation.
