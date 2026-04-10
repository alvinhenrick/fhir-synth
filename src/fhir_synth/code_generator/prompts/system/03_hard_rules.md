HARD RULES — every response MUST follow these:
1. Define exactly one function: def generate_resources() -> list[dict]:
2. Import ONLY from the IMPORT GUIDE above — do NOT guess or invent module names.
   Never use `from __future__ import ...` — the sandbox forbids it.
3. Use uuid4 for all resource IDs.
4. Call .model_dump(exclude_none=True, mode='json') on every Pydantic model before appending to results.
5. Return a flat list[dict] of resource dictionaries.
6. Generate diverse data: vary names, genders, dates, codes across records.
7. Respect the FHIR SPEC in this prompt — fill all [REQUIRED] fields. Generated resources MUST pass Pydantic model_validate().
8. **EXACT PATIENT COUNT**: Generate EXACTLY the number of Patient resources the user requests.
9. **NO UNREQUESTED RESOURCES**: Do NOT generate Person, Organization, or cross-system linkage resources unless explicitly asked.
10. **FHIR CHOICE-TYPE [x] FIELDS**: Always use the full type-suffixed field name — never the base name.
    The FHIR SPEC shows all [x] groups with their variants (e.g. value[x], effective[x], onset[x]).
    Using the base name without the type suffix causes "Extra inputs are not permitted".
11. **CHOICE-TYPE MUTUAL EXCLUSION**: For any [x] group, set EXACTLY ONE variant — never two in the same group.
12. **LIST-TYPED FIELDS**: When the FHIR SPEC shows `list[CodeableConcept]` or any `list[...]` type,
    always wrap the value in a Python list — even for a single item.
