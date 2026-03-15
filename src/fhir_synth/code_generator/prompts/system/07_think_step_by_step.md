THINK STEP-BY-STEP:
1. Parse requirement → identify resource types needed (Patient, Condition, etc.)
2. Plan imports → check correct module paths (fhir.resources.R4B.{module})
3. Design data flow → determine relationships (Patient IDs → references)
4. Choose codes → select appropriate ICD-10/LOINC/RxNorm codes
5. Plan patient variation → ensure age, gender, race, language, insurance diversity
6. Plan comorbidity clusters → select realistic co-occurring conditions
7. Implement function → write generate_resources() with a proper structure
8. Validate → ensure all references are valid, all models use .model_dump(exclude_none=True, mode='json')
9. EVERY resource dict MUST have a "resourceType" key — this is checked automatically.
   Fill ALL required fields for each resource type (see FHIR SPEC in the prompt).

Return ONLY the Python code, no explanation text.

