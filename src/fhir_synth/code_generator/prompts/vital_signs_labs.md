# Vital Signs & Observation Panels

## Vital Signs

Use the FHIR Vital Signs profile (LOINC panel 85353-1).

| Vital Sign | LOINC | Realistic Range | Unit |
|-----------|-------|----------------|------|
| Blood pressure (panel) | 85354-9 | — | — |
| Systolic BP | 8480-6 | 90–200 | mmHg |
| Diastolic BP | 8462-4 | 50–120 | mmHg |
| Heart rate | 8867-4 | 40–150 | /min |
| Respiratory rate | 9279-1 | 12–30 | /min |
| Temperature | 8310-5 | 35.5–40.5 | Cel |
| Oxygen saturation | 2708-6 | 85–100 | % |
| Height | 8302-2 | varies | cm |
| Weight | 29463-7 | varies | kg |
| BMI | 39156-5 | varies | kg/m2 |
| Head circumference (pediatric) | 9843-4 | varies | cm |

- Blood pressure uses `component[]` for systolic + diastolic.
- Vary by age/condition (athletes, elderly, tachycardia).
- Use `Observation.category` = `"vital-signs"` (`http://terminology.hl7.org/CodeSystem/observation-category`)
- Include `Observation.interpretation` codes: N=Normal, H=High, L=Low, HH=Critical High, LL=Critical Low

## Lab Panels

Use realistic lab results with proper reference ranges.

### CBC

| Test | LOINC |
|------|-------|
| WBC | 6690-2 |
| RBC | 789-8 |
| Hemoglobin | 718-7 |
| Hematocrit | 4544-3 |
| Platelets | 777-3 |

### BMP

| Test | LOINC |
|------|-------|
| Sodium | 2951-2 |
| Potassium | 2823-3 |
| Chloride | 2075-0 |
| CO2 | 2028-9 |
| BUN | 3094-0 |
| Creatinine | 2160-0 |
| Glucose | 2345-7 |
| Calcium | 17861-6 |

### CMP (BMP plus)

| Test | LOINC |
|------|-------|
| ALT | 1742-6 |
| AST | 1920-8 |
| Alk Phos | 6768-6 |
| Total Bilirubin | 1975-2 |
| Albumin | 1751-7 |
| Total Protein | 2885-2 |

### Lipid Panel

| Test | LOINC |
|------|-------|
| Total cholesterol | 2093-3 |
| LDL | 13457-7 |
| HDL | 2085-9 |
| Triglycerides | 2571-8 |

### Other

| Test | LOINC |
|------|-------|
| HbA1c | 4548-4 (range 4.0–14.0 %) |
| Urinalysis | 24356-8 (panel) |
| COVID-19 PCR | 94500-6 |
| COVID-19 antigen | 94558-4 |

- Include `referenceRange` with low/high values and text (e.g. "4.5-11.0 x10^9/L").
- Flag abnormal results with interpretation codes.

