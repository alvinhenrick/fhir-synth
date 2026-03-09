The following Python code failed with this error:

ERROR:
$error

CODE:
$code

$fhir_imports

SANDBOX CONSTRAINTS — only these imports are allowed:
- Modules: $allowed_list, $allowed_prefixes
- FORBIDDEN builtins: eval(), exec(), open(), compile(), globals(), __import__()

If the error is "Import of X is not allowed", replace that import with an allowed alternative.
If the error is a Pydantic ValidationError, fix the invalid field value.
If the error mentions "Instant value string does not match spec regex", add a timezone offset
  (e.g. use datetime.now(datetime.timezone.utc).isoformat() or append "Z").
If the error mentions "missing 'resourceType'", ensure you call .model_dump(exclude_none=True) on
  every Pydantic model — this automatically includes resourceType.
If the error mentions "returned empty list", ensure generate_resources() returns a non-empty list.
If the error mentions "is required", add the missing required field (check the FHIR SPEC).
If the error mentions "clinicalStatus" or "verificationStatus", ensure these CodeableConcept
  fields use the correct system URLs and codes (see HARD RULES).
If the error relates to Extension or US Core profiles, ensure nested extensions use the correct
  structure with url and value[x] fields.
If the error mentions "dataAbsentReason", ensure it's only set when value[x] is absent.

Fix the code so it runs without errors. Keep the same function signature:
  def generate_resources() -> list[dict]:
Return ONLY the corrected Python code, no explanation.

