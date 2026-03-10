HARD RULES — every response MUST follow these:
1. Define exactly one function: def generate_resources() -> list[dict]:
2. Import from fhir.resources.R4B using ONLY the exact module paths listed in the IMPORT GUIDE.
   Do NOT guess or invent module names.
3. Use uuid4 for all resource IDs.
4. Call .model_dump(exclude_none=True, mode='json') on every Pydantic model before appending to results.
5. Return a flat list[dict] of resource dictionaries.
6. Do NOT use external data files — generate everything inline with random.
7. **CRITICAL DATETIME RULE**: ALL DateTime/Instant fields with time components MUST include timezone.
   - Use datetime.now(timezone.utc) or datetime(..., tzinfo=timezone.utc).isoformat()
   - Date-only fields (like birthDate) use date(...).isoformat()
   - Define a dt_iso() helper to ensure timezone-aware strings (see EXAMPLE below)
   - ✓ VALID: "2025-03-08T10:30:00+00:00" or "2025-03-08T10:30:00Z" or "2025-03-08"
   - ✗ INVALID: "2025-03-08T10:30:00" (time without timezone) — this will FAIL validation
8. Use only allowed modules (see SANDBOX CONSTRAINTS above) plus fhir.resources.
9. Wrap numeric FHIR values with Decimal (from decimal import Decimal) not float.
10. Generate diverse data: vary names, genders, dates, codes across records.
11. Respect the FHIR SPEC provided with each prompt — it lists required fields, reference
    fields, and types per resource. Your generated resources MUST pass Pydantic model_validate()
    for their resource type.

