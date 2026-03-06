# Medication Realism

Generate prescriptions reflecting real clinical practice.

## Polypharmacy

Geriatric patients commonly take 5–15 medications. Include:

| Category | Medication | RxNorm |
|----------|-----------|--------|
| Antihypertensives | Lisinopril | 29046 |
| Antihypertensives | Amlodipine | 17767 |
| Antihypertensives | Metoprolol | 6918 |
| Diabetes | Metformin | 6809 |
| Diabetes | Glipizide | 4815 |
| Diabetes | Insulin glargine | 261551 |
| Statins | Atorvastatin | 83367 |
| Statins | Rosuvastatin | 301542 |
| Anticoagulants | Warfarin | 11289 |
| Anticoagulants | Apixaban | 1364430 |
| Anticoagulants | Rivaroxaban | 1114195 |
| Pain | Acetaminophen | 161 |
| Pain | Ibuprofen | 5640 |
| Pain | Tramadol | 10689 |
| Psych | Sertraline | 36437 |
| Psych | Escitalopram | 321988 |
| Psych | Quetiapine | 51272 |
| GI | Omeprazole | 7646 |
| GI | Pantoprazole | 40790 |

## Dosage & Administration

- **Dosage forms**: Tablets, capsules, injections, inhalers, patches, liquids, eye drops. Use proper route codes from `http://snomed.info/sct` (26643006=Oral, 78421000=Intramuscular, etc.)
- **Frequency**: Include `timing.repeat` with `frequency`, `period`, `periodUnit`, `when` (AC, PC, HS, etc.)
- **Status**: active, on-hold, cancelled, completed, entered-in-error, stopped, draft
- **Intent**: order, plan, original-order, reflex-order, filler-order, instance-order
- **PRN medications**: Set `asNeededBoolean=True` or `asNeededCodeableConcept` with indication

## Drug Allergies

Include medication allergies in `AllergyIntolerance`: Penicillin, Sulfa, NSAIDs with reaction severity (mild, moderate, severe) and manifestation codes.

