---
name: medications
description: Generate realistic medication data across the full FHIR R4B medication family — Medication (the drug itself), MedicationRequest (prescriptions), MedicationDispense (pharmacy fills), MedicationAdministration (given doses), MedicationStatement (patient-reported use), and MedicationKnowledge (drug reference). Covers RxNorm codes, dosage, route, timing, polypharmacy, PRN, refills, and drug allergies. Use when user mentions medication, prescription, drug, pharmacy, dispense, dispensing, administration, refill, RxNorm, NDC, insulin, metformin, statin, antibiotic, antihypertensive, opioid, SSRI, inhaler, PRN, or polypharmacy.
resource_types: [Medication, MedicationRequest, MedicationDispense, MedicationAdministration, MedicationStatement, MedicationKnowledge]
always: false
---

# Medication Realism

Generate medication data across the full FHIR R4B medication family. Each
resource has a distinct role — pick the right one for the clinical scenario.

## Resource selection guide

| Resource | When to use |
|---|---|
| `MedicationRequest` | Prescription / order. The default for outpatient and discharge meds. **US Core profiled.** |
| `Medication` | The drug itself as a referenced resource (when the same drug is referenced by multiple Requests/Dispenses, or when it carries batch/lot/expiration info). For simple cases, use inline `medicationCodeableConcept` on the Request and skip this resource. |
| `MedicationDispense` | Pharmacy fill event — what was actually dispensed (drug, quantity, days supply, dispenser). One Request can have many Dispenses (refills). |
| `MedicationAdministration` | A single given dose — inpatient nurse documents administration, IV infusion, immunization-adjacent. Use for inpatient/ED scenarios. |
| `MedicationStatement` | Patient-reported / reconciled history ("patient says they take metformin daily"). Use for medication-reconciliation, intake forms, home meds. |
| `MedicationKnowledge` | Drug reference data (rarely needed for synthetic patient data — only for formulary/catalog scenarios). |

## Cross-resource relationships

```
MedicationRequest  ──authorizingPrescription──▶  MedicationDispense
        │                                                │
        └──── medication[x] ───▶ Medication ◀────────────┘
                                       │
MedicationAdministration ──request──▶ MedicationRequest
MedicationStatement ──basedOn──▶ MedicationRequest (optional)
```

- `medicationCodeableConcept` (inline RxNorm) vs `medicationReference` (link to `Medication` resource) — both are valid on Request/Dispense/Administration/Statement. Prefer inline for simplicity unless you need the shared `Medication` resource for batch/lot or multiple referencers.

## Code systems

- **RxNorm** (`http://www.nlm.nih.gov/research/umls/rxnorm`) — primary US ingredient/strength code system. Always include for clinical drugs.
- **NDC** (`http://hl7.org/fhir/sid/ndc`) — package-level code (used on `MedicationDispense.medicationCodeableConcept` to reflect what was actually pulled from the shelf).
- **SNOMED CT** for route codes (e.g. `26643006`=Oral, `78421000`=Intramuscular, `47625008`=Intravenous).

## Realism rules

- **POLYPHARMACY**: Geriatric patients commonly take 5–15 medications. Common combinations:
  * Antihypertensives: Lisinopril (RxNorm 29046), Amlodipine (17767), Metoprolol (6918)
  * Diabetes: Metformin (6809), Glipizide (4815), Insulin glargine (261551)
  * Statins: Atorvastatin (83367), Rosuvastatin (301542)
  * Anticoagulants: Warfarin (11289), Apixaban (1364430), Rivaroxaban (1114195)
  * Pain: Acetaminophen (161), Ibuprofen (5640), Tramadol (10689)
  * Psych: Sertraline (36437), Escitalopram (321988), Quetiapine (51272)
  * GI: Omeprazole (7646), Pantoprazole (40790)
- **DOSAGE FORMS**: Tablets, capsules, injections, inhalers, patches, liquids, eye drops.
- **FREQUENCY**: Include `dosageInstruction.timing.repeat` with `frequency`, `period`, `periodUnit`, `when` (AC, PC, HS, etc.).
- **MedicationRequest.status**: `active`, `on-hold`, `cancelled`, `completed`, `entered-in-error`, `stopped`, `draft`.
- **MedicationRequest.intent**: `proposal`, `plan`, `order`, `original-order`, `reflex-order`, `filler-order`, `instance-order`, `option`.
- **MedicationDispense.status**: `preparation`, `in-progress`, `cancelled`, `on-hold`, `completed`, `entered-in-error`, `stopped`, `declined`, `unknown`.
- **MedicationDispense.daysSupply**: Realistic — 30/90 days for chronic outpatient; smaller for controlled substances or trials.
- **MedicationDispense.quantity**: Numeric `value` + RxNorm/UCUM unit. Match the days supply × frequency.
- **MedicationDispense.authorizingPrescription**: Reference back to the originating `MedicationRequest`. Multiple dispenses (refills) share one Request.
- **MedicationAdministration.effectiveDateTime**: When the dose was given. For infusions, use `effectivePeriod` with start/end.
- **MedicationAdministration.performer.actor**: Reference the administering Practitioner (nurse, RN).
- **MedicationStatement.status**: `active`, `completed`, `entered-in-error`, `intended`, `stopped`, `on-hold`, `unknown`, `not-taken`.
- **MedicationStatement.dateAsserted**: When the statement was recorded (often the visit date).
- **PRN medications**: Set `dosageInstruction.asNeededBoolean=True` or `asNeededCodeableConcept` with an indication.
- **REQUESTER** (US Core must-support on MedicationRequest): Always include `requester`, referencing the prescribing Practitioner resource. Create a Practitioner if one does not already exist in the bundle.
- **DRUG ALLERGIES** in `AllergyIntolerance`: Include medication allergies (Penicillin, Sulfa, NSAIDs) with reaction severity (mild, moderate, severe) and manifestation codes.
