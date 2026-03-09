HARD RULES — every response MUST follow these:
1. Define exactly one function: def generate_resources() -> list[dict]:
2. Import from fhir.resources.R4B using ONLY the exact module paths listed in the IMPORT GUIDE.
   Do NOT guess or invent module names.
3. Use uuid4 for all resource IDs.
4. Call .model_dump(exclude_none=True) on every Pydantic model before appending to results.
5. Return a flat list[dict] of resource dictionaries.
6. Do NOT use external data files — generate everything inline with random.
7. Use only allowed modules (see SANDBOX CONSTRAINTS above) plus fhir.resources.
8. Wrap numeric FHIR values with Decimal (from decimal import Decimal) not float.
9. Generate diverse data: vary names, genders, dates, codes across records.
10. Respect the FHIR SPEC provided with each prompt — it lists required fields, reference
    fields, and types per resource. Your generated resources MUST pass Pydantic model_validate()
    for their resource type.

