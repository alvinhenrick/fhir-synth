# Encounter Realism

Model real clinical workflows.

## Class Codes

System: `http://terminology.hl7.org/CodeSystem/v3-ActCode`

| Code | Meaning |
|------|---------|
| AMB | Ambulatory |
| IMP | Inpatient |
| EMER | Emergency |
| HH | Home health |
| VR | Virtual / telehealth |
| OBSENC | Observation encounter |
| SS | Short stay |
| PRENC | Pre-admission |
| ACUTE | Inpatient acute |
| NONAC | Inpatient non-acute |

## Encounter Types (SNOMED)

| Code | Meaning |
|------|---------|
| 308335008 | Office visit |
| 183452005 | ER visit |
| 32485007 | Hospital admission |
| 185347001 | Encounter for problem |
| 270427003 | Routine child health |
| 185349003 | Well woman |
| 410620009 | Well child |
| 11429006 | Consultation |
| 371883000 | Outpatient procedure |

## Status Values

planned, arrived, triaged, in-progress, onleave, finished, cancelled, entered-in-error

## Hospitalization

Include admit/discharge details with `admitSource` and `dischargeDisposition`:
- **admitSource**: home, er, born-in-hospital, transfer
- **dischargeDisposition**: home, snf (skilled nursing), rehab, expired, hospice

## Additional Rules

- Use `Encounter.reasonCode` with appropriate SNOMED/ICD-10 codes.
- Realistic `Encounter.period` — office visits ~15–60 min, ER 2–8 hrs, inpatient 1–14 days, ICU 3–30 days.
- Mark virtual encounters with `serviceType` and use VR class code. Add location with type "VR" (virtual).
- Generate multiple encounters per patient: longitudinal care with follow-ups.

