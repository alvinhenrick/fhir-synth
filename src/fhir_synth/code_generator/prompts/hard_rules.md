# Hard Rules

Every response MUST follow these rules:

1. Define exactly one function: `def generate_resources() -> list[dict]:`
2. Import from `fhir.resources.R4B` using ONLY the exact module paths listed in the IMPORT GUIDE provided with each prompt. Do NOT guess module names — many classes live in parent modules:
   - ✓ CORRECT: `from fhir.resources.R4B.timing import Timing, TimingRepeat`
   - ✗ WRONG: `from fhir.resources.R4B.timingrepeat import TimingRepeat` (module doesn't exist)
3. Use `uuid4` for all resource IDs.
4. Call `.model_dump(exclude_none=True)` on every Pydantic model before appending to results.
5. Return a flat `list[dict]` of resource dictionaries.
6. Do NOT use external data files — generate everything inline with random.
7. All dates must be valid ISO-8601 strings.
   FHIR "instant" fields (e.g. `issued`, `lastUpdated`, `recorded`) MUST include a timezone offset:
   - ✓ CORRECT: `"2026-02-28T10:30:00+00:00"` or `"2026-02-28T10:30:00Z"`
   - ✗ WRONG: `"2026-02-28T10:30:00"` or `"2026-02-28T10:30:00.123456"` (missing timezone)
   - Use `datetime.now(datetime.timezone.utc).isoformat()` or append `"Z"` for UTC timestamps.
8. Use standard code systems: ICD-10-CM, SNOMED CT, LOINC, RxNorm, CPT where appropriate.
9. Every clinical resource (Condition, Observation, MedicationRequest, Procedure, Encounter, DiagnosticReport) MUST reference a Patient via `subject` or `patient`.
10. Use only allowed modules (see SANDBOX CONSTRAINTS above) plus `fhir.resources`.
11. Wrap numeric FHIR values with `Decimal` (`from decimal import Decimal`) not float.
12. Generate diverse data: vary names, genders, dates, codes across records.
13. When adding metadata (security, tags, profiles), use the `Meta` model from `fhir.resources.R4B.meta` and set it on resources before calling `.model_dump()`.

