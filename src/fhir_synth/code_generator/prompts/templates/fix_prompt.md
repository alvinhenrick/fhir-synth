The following Python code failed with this error:

ERROR:
$error

CODE:
$code

$fhir_imports

FHIR SPEC (fields with types — see DATA TYPE FORMAT RULES):
$fhir_spec

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
- If the error mentions "DateTime value string does not match spec regex" or
  "Instant value string does not match spec regex": you created a naive datetime.
  Always make datetimes timezone-aware before calling .isoformat():
    dt = datetime(2025, 3, 8, 10, 30, tzinfo=timezone.utc)
    dt_iso = dt.isoformat()
  Or define a helper:
    def dt_iso(v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()

Fix the code so it runs without errors. Keep the same function signature:
  def generate_resources() -> list[dict]:
Return ONLY the corrected Python code, no explanation.
