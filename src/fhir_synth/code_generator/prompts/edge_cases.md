# Edge Cases & Special Populations

Include these to ensure robustness:

## Neonates & Infants
Use age in days/weeks, weight in grams, Apgar scores (LOINC 9274-2, 9271-8), gestational age, birth weight classification (SNOMED), neonatal conditions (P07.3 Preterm, P59.9 Jaundice, P22.0 RDS).

## Pregnant Patients
Include pregnancy-related conditions (O24.4 Gestational DM, O13 Gestational HTN, O80 Spontaneous delivery), gravida/para status, EDD, prenatal labs (blood type, Rh factor, GBS screen), Pregnancy status observation (LOINC 82810-3).

## Elderly / Geriatric
Multiple comorbidities, polypharmacy (5+ meds), functional status (ADL/IADL scores), fall risk assessments, cognitive screening (MMSE/MoCA), advance directives, goals of care.

## Behavioral Health
Substance use disorders (F10–F19 series), depression screening (PHQ-9 LOINC 44249-1), anxiety screening (GAD-7 LOINC 69737-5), suicide risk screening (Columbia LOINC 93267-1), psychiatric diagnoses, psychotropic medications.

## Disability & Functional Status
Include functional status observations, assistive device use, disability conditions. Use Observation category `"functional-status"`.

## Rare / Chronic Conditions
Sickle cell (D57.1), Cystic fibrosis (E84.0), Lupus (M32.9), Rheumatoid arthritis (M06.9), Multiple sclerosis (G35), HIV (B20), Hepatitis C (B18.2), Cancer staging (use TNM codes), Organ transplant status (Z94.*).

## Multi-Organ Patients
Patients with conditions spanning multiple organ systems (e.g., diabetic nephropathy + retinopathy + neuropathy: E11.21 + E11.311 + E11.40).

## Deceased Patients
Include cause of death, death date, relevant final encounter.

## Patients With No Data
Some patients may have only demographics (newly registered).

