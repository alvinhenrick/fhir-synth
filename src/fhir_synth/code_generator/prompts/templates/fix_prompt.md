The following Python code failed with this error:

ERROR:
$error

CODE:
$code

$fhir_imports

FHIR SPEC (fields with types — see DATA TYPE FORMAT RULES):
$fhir_spec

AVAILABLE MODULES — only these imports exist in the sandbox:
- $allowed_list, $allowed_prefixes
- eval(), exec(), open(), compile(), globals(), __import__() are unavailable.

Read the error carefully and fix the code:
- If "Import of X is not allowed", replace with an allowed alternative.
- If "missing 'resourceType'", call .model_dump(exclude_none=True, mode='json') on Pydantic models.
- If "returned empty list", ensure generate_resources() returns a non-empty list.
- If it is a Pydantic ValidationError, the error tells you exactly which field on which
  resource type is invalid and why. Fix that field value so it passes model_validate().
  The FHIR SPEC and IMPORT GUIDE provided above have the correct types and constraints.

⚠️  MOST COMMON ERROR — DateTime regex validation failure:
- If the error mentions "DateTime value string does not match spec regex" or
  "Instant value string does not match spec regex": YOU CREATED A NAIVE DATETIME (missing timezone).
- FHIR DateTime fields with time components MUST include timezone: +00:00 or Z
- ✗ WRONG: datetime.now().isoformat() → "2025-03-08T10:30:00" (no timezone!)
- ✓ CORRECT: datetime.now(timezone.utc).isoformat() → "2025-03-08T10:30:00+00:00"
- BEST PRACTICE: Always define this helper and use it for ALL datetime fields:
    def dt_iso(v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return v.isoformat()
  Then use: period=Period(start=dt_iso(start_dt), end=dt_iso(end_dt))
- Date-only fields (birthDate, onsetDate) should use date().isoformat(), NOT datetime

⚠️  CHOICE-TYPE MUTUAL EXCLUSION ERROR:
- If the error mentions "one field value is expected from this list [...] but got multiple"
  or "Choice-type ... conflict": you set MORE THAN ONE variant of a choice-type [x] field.
- FHIR [x] fields (deceased[x], value[x], onset[x], effective[x], medication[x], born[x],
  age[x]) allow EXACTLY ONE variant per resource. Remove the extra fields, keep only the
  most specific one.
- ✗ WRONG: FamilyMemberHistory(deceasedBoolean=True, deceasedAge=Age(...))
- ✓ FIX:   FamilyMemberHistory(deceasedAge=Age(value=Decimal(62), unit="a", system="http://unitsofmeasure.org", code="a"))
  Keep deceasedAge (more informative) and REMOVE deceasedBoolean entirely.

Fix the code so it runs without errors. Keep the same function signature:
  def generate_resources() -> list[dict]:
Return ONLY the corrected Python code, no explanation.
