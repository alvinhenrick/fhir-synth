# Social Determinants of Health (SDOH)

Generate SDOH Observations and Conditions using Gravity Project value sets and SDOH Clinical Care IG categories:

## Screening Codes

| Category | LOINC | SNOMED | ICD-10 |
|----------|-------|--------|--------|
| Food insecurity | 88124-3 (Food insecurity risk) | 733423003 | — |
| Housing instability | 71802-3 | 32911000 | Z59.0 (Homelessness) |
| Transportation | 93030-3 | — | Z59.82 |
| Financial strain | 76513-1 | — | Z59.7 (Insufficient social insurance) |
| Social isolation | 93029-5 | — | Z60.2 |
| Education level | 82589-3 | — | — |
| Employment status | 67875-5 | — | — |
| Intimate partner violence | 76499-3 | — | Z63.0 |
| Stress | 76542-0 | — | — |
| Veteran status | 63028-3 | — | — |

## Encoding Rules

- Encode SDOH screening results as Observations with category = `http://hl7.org/fhir/us/sdoh-clinicalcare/CodeSystem/SDOHCC-CodeSystemTemporaryCodes` or `social-history` (`http://terminology.hl7.org/CodeSystem/observation-category`)
- Link SDOH Conditions to Goals and ServiceRequests for care coordination

