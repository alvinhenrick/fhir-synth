---
name: longitudinal
description: Temporal disease progression patterns for longitudinal FHIR data generation. Covers encounter frequency, lab value trajectories, medication escalation logic, and vital sign trends for common chronic conditions. Use when generating patients with follow-up visits, multi-year histories, or disease progression over time.
keywords: [longitudinal, follow-up, progression, timeline, history, chronic, years, months, visits, encounters, trend, trajectory, worsening, improving, escalation, titration, quarterly, annual, baseline, follow up, over time, disease course, treatment response]
resource_types: [Patient, Encounter, Observation, Condition, MedicationRequest, Procedure, DiagnosticReport, CarePlan, Goal, ServiceRequest]
always: false
---

# Longitudinal Clinical Data Generation

Use this skill whenever a prompt requests multi-visit patient histories, disease progression over time, or treatment response trajectories. Populate `PatientProfile.timeline` with `EncounterEvent` entries and set `ClinicalPlan.time_span_months`.

## Core Principles

- **Encounter-anchored**: every lab, vital, procedure, and medication change belongs to a specific encounter (`month_offset`)
- **Causal consistency**: lab values must reflect clinical reality — HbA1c drops after treatment, creatinine rises with CKD progression, LDL falls on statins
- **Realistic timing**: encounter frequency mirrors clinical guidelines, not arbitrary intervals
- **Medication lifecycle**: meds have start dates, may be titrated, and sometimes stopped with reasons

---

## Encounter Frequency by Condition

| Condition | Stable frequency | Uncontrolled / active frequency |
|---|---|---|
| Type 2 Diabetes | Every 6 months | Every 3 months |
| Hypertension | Every 6 months | Every 1–3 months during titration |
| Heart Failure | Every 3 months | Every 1–4 weeks (acute) |
| CKD Stage 3–4 | Every 3–6 months | Every 1–3 months |
| CKD Stage 5 | Monthly | Weekly (pre-dialysis) |
| COPD (stable) | Every 6 months | Every 1–3 months |
| Asthma (controlled) | Annually | Every 1–3 months |
| Depression | Every 1–3 months (active) | Every 2–4 weeks (acute) |
| Hyperlipidemia | Annually | Every 3–6 months during titration |
| Post-MI | Week 1, Week 6, Month 3, then annually | |
| Oncology (active treatment) | Per cycle (every 3–6 weeks) | Per protocol |

---

## Type 2 Diabetes Mellitus (T2DM)

### Key LOINC codes
| Test | LOINC | Typical range | Target |
|---|---|---|---|
| HbA1c | 4548-4 | 4.0–14.0 % | <7.0% |
| Fasting glucose | 1558-6 | 70–500 mg/dL | 80–130 mg/dL |
| eGFR | 62238-1 | 15–120 mL/min/1.73m² | >60 |
| Urine albumin/creatinine | 9318-7 | 0–300 mg/g | <30 |
| LDL-C | 2089-1 | 60–220 mg/dL | <100 mg/dL |

### Typical HbA1c trajectory
- **Diagnosis**: 7.5–12.0% (median ~9.0%)
- **After 3 months on Metformin 500mg**: drops ~0.5–1.0%
- **After 6 months on Metformin 1000mg**: drops additional 0.5–1.0%
- **Controlled (target reached)**: 6.5–7.0%, stable
- **Suboptimal despite Metformin**: >8.0% → trigger GLP-1 or SGLT-2 addition
- **Requiring insulin**: >9.0% on dual therapy → add basal insulin

### Medication escalation (RxNorm codes)
```
Step 1: Metformin 500mg BID (RxNorm: 6809)   → at diagnosis
Step 2: Metformin 1000mg BID (RxNorm: 6809)  → 3 months if HbA1c > 7.5%
Step 3: Add Semaglutide 0.5mg (RxNorm: 2200644) OR Empagliflozin 10mg (RxNorm: 1544385)
        → 6–12 months if HbA1c > 7.5% on max Metformin
Step 4: Add Glargine insulin 10 units QHS (RxNorm: 274783)
        → if HbA1c > 9.0% on dual oral therapy
```

### Example 18-month T2DM timeline (month_offset values)
- 0: Diagnosis encounter — HbA1c 9.2%, start Metformin 500mg
- 3: Follow-up — HbA1c 8.1%, titrate to Metformin 1000mg, renal panel
- 6: Follow-up — HbA1c 7.4%, continue, annual labs (lipids, uACR)
- 12: Annual — HbA1c 7.1%, well-controlled, foot exam, dilated eye referral
- 18: Follow-up — HbA1c 6.9%, target maintained

---

## Hypertension (HTN)

### Key LOINC codes
| Vital/Test | LOINC | Normal | Target (HTN) |
|---|---|---|---|
| Systolic BP | 8480-6 | 90–120 mm[Hg] | <130 mm[Hg] |
| Diastolic BP | 8462-4 | 60–80 mm[Hg] | <80 mm[Hg] |
| Serum potassium | 2823-3 | 3.5–5.0 mEq/L | monitor on ACE/ARB |
| Serum creatinine | 2160-0 | 0.6–1.2 mg/dL | monitor on ACE/ARB |

### BP trajectory on treatment
- **Uncontrolled**: 155–180 / 95–110 mm[Hg]
- **4 weeks on ACEI/ARB**: 10–15 mm[Hg] reduction systolic
- **6–8 weeks controlled**: <130/80
- **Resistant HTN** (>3 drugs): add spironolactone or clonidine

### Medication escalation (RxNorm codes)
```
Step 1: Lisinopril 10mg QD (RxNorm: 29046)   → first-line
Step 2: Amlodipine 5mg QD (RxNorm: 17767)    → add if BP > 140/90 at 4 weeks
Step 3: Hydrochlorothiazide 25mg QD (RxNorm: 5487) → add if BP > 140/90 on 2 agents
Step 4: Spironolactone 25mg QD (RxNorm: 9997) → resistant HTN
```

---

## Chronic Kidney Disease (CKD)

### Key LOINC codes
| Test | LOINC | Stage 3a | Stage 3b | Stage 4 | Stage 5 |
|---|---|---|---|---|---|
| eGFR | 62238-1 | 45–59 | 30–44 | 15–29 | <15 |
| Serum creatinine | 2160-0 | 1.2–1.8 | 1.8–2.5 | 2.5–5.0 | >5.0 |
| Serum potassium | 2823-3 | 3.5–5.0 | 3.5–5.2 | 4.0–5.5 | 4.5–6.5 |
| Hemoglobin | 718-7 | 11–14 | 10–13 | 9–12 | 8–11 g/dL |
| Phosphorus | 2777-1 | normal | 3.5–5.0 | 4.0–6.0 | 4.5–8.0 mg/dL |

### Progression rate (with diabetes/HTN): ~3–5 mL/min/1.73m²/year decline in eGFR
- Medications: ACE inhibitor (nephroprotective) + phosphate binders at Stage 4
- Anemia: start erythropoietin when Hb < 10 g/dL
- At eGFR < 20: nephrology referral, AV fistula planning

---

## Heart Failure (HFrEF)

### Key LOINC codes
| Test | LOINC | Target |
|---|---|---|
| NT-proBNP | 33762-6 | <300 pg/mL (stable) |
| LVEF (echo) | 18009-9 | >40% |
| Serum sodium | 2951-2 | 135–145 mEq/L |
| BUN | 3094-0 | 7–20 mg/dL |
| Weight | 29463-7 | Monitor daily (0.5kg increase = decompensation) |

### Medication escalation (GDMT — Guideline-Directed Medical Therapy)
```
Pillar 1: Carvedilol 6.25mg BID → titrate to 25mg BID (RxNorm: 20352)
Pillar 2: Lisinopril 5mg QD → titrate to 40mg QD (RxNorm: 29046)
Pillar 3: Spironolactone 25mg QD (RxNorm: 9997) — MRA
Pillar 4: Dapagliflozin 10mg QD (RxNorm: 2371643) — SGLT2i
```
- Diuresis: Furosemide 40mg QD (RxNorm: 4603) — add for volume overload
- Decompensation encounter: weight +3kg, dyspnea → IV diuresis → discharge with uptitration

---

## COPD

### Key LOINC codes
| Test | LOINC |
|---|---|
| FEV1/FVC ratio | 19926-5 |
| O2 saturation (SpO2) | 2708-6 |
| Smoking pack-years | 64234-8 |

### GOLD staging by FEV1 (% predicted)
- GOLD 1: ≥80% (mild)
- GOLD 2: 50–79% (moderate) — most common at diagnosis
- GOLD 3: 30–49% (severe)
- GOLD 4: <30% (very severe)

### Medication escalation
```
GOLD 1–2: SABA PRN → Tiotropium 18mcg QD (RxNorm: 274091)
GOLD 3: LABA + LAMA → Budesonide/Formoterol 160/4.5 BID (RxNorm: 895994)
GOLD 4: Triple therapy + pulmonology referral + O2 assessment
```
- Exacerbation: Prednisone 40mg x5d + Azithromycin 500mg x5d

---

## Depression (MDD)

### Key LOINC codes
| Assessment | LOINC | Score range | Severe |
|---|---|---|---|
| PHQ-9 | 44261-6 | 0–27 | ≥20 |
| GAD-7 | 69737-5 | 0–21 | ≥15 |

### Treatment timeline
- **Weeks 0–2**: Start SSRI (Sertraline 50mg QD, RxNorm: 36437)
- **Week 4**: Partial response → titrate to 100mg
- **Week 8**: PHQ-9 reassessment — if <50% improvement, augment or switch
- **Week 12**: SNRI switch (Venlafaxine 75mg, RxNorm: 39786) if SSRI failure
- Remission: PHQ-9 < 5

---

## Hyperlipidemia

### Key LOINC codes
| Lipid | LOINC | Target (high-risk) |
|---|---|---|
| LDL-C | 2089-1 | <70 mg/dL (ASCVD), <100 mg/dL (moderate) |
| HDL-C | 2085-9 | >40 (M), >50 (F) mg/dL |
| Triglycerides | 2571-8 | <150 mg/dL |
| Total cholesterol | 2093-3 | <200 mg/dL |

### Medication escalation
```
Step 1: Atorvastatin 40mg QD (RxNorm: 617310) — high-intensity statin
Step 2: Atorvastatin 80mg QD — maximum intensity
Step 3: Add Ezetimibe 10mg QD (RxNorm: 341248) — if LDL > 70 on max statin
Step 4: Add Evolocumab 140mg SQ Q2W (PCSK9i, RxNorm: 1860487) — very high risk
```
- LDL reduction: statin ~50%, + ezetimibe additional ~15–20%
- Check LFTs and CK at baseline; recheck lipids at 6–12 weeks after any change

---

## Vital Signs by Age Group (LOINC codes)

| Vital | LOINC | Adult normal | Elderly (65+) |
|---|---|---|---|
| Heart rate | 8867-4 | 60–100 bpm | 60–100 bpm |
| Respiratory rate | 9279-1 | 12–20 /min | 12–20 /min |
| Body temperature | 8310-5 | 36.5–37.2 °C | 36.0–37.0 °C |
| BMI | 39156-5 | 18.5–24.9 kg/m² | 22–30 kg/m² |
| Weight | 29463-7 | varies | varies |
| Height | 8302-2 | varies | varies |
| O2 saturation | 2708-6 | 95–100 % | 94–99 % |

---

## Generating Temporally Consistent Lab Trends

When building a timeline, follow these rules:

1. **Treatment response lag**: labs improve 4–12 weeks after medication start, not immediately
2. **Regression to mean**: untreated values drift toward disease-typical ranges over time
3. **Comorbidity interactions**: CKD raises creatinine AND lowers eGFR simultaneously; HF raises BNP AND lowers sodium
4. **Normal variation**: add ±5–10% random variation to repeated labs — perfect reproducibility is unrealistic
5. **Critical values trigger encounters**: HbA1c > 10%, K+ > 6.0, Na+ < 125 → urgent/emergency encounter

### Example causal chain (T2DM + HTN + CKD)
```
Month 0:  HbA1c 10.2%, BP 168/102, eGFR 52, uACR 85  → start Metformin + Lisinopril
Month 3:  HbA1c 8.9%,  BP 145/92,  eGFR 49, uACR 62  → titrate both, add Amlodipine
Month 6:  HbA1c 7.8%,  BP 132/82,  eGFR 48, uACR 45  → on track, continue
Month 12: HbA1c 7.1%,  BP 128/78,  eGFR 46, uACR 38  → well-controlled
Month 18: HbA1c 7.4%,  BP 130/80,  eGFR 44, uACR 42  → slight CKD progression
Month 24: HbA1c 7.2%,  BP 128/76,  eGFR 41, uACR 55  → nephrology referral
```

---

## Encounter Class Selection

| Scenario | encounter_class |
|---|---|
| Routine office visit, follow-up | AMB |
| Emergency department visit | EMER |
| Hospital admission (>24h) | IMP |
| Observation stay, short stay | OBSENC |
| Telemedicine, phone visit | VR |

---

## Stage 2 Code Generation Notes

When generating code from a longitudinal plan:

1. Compute encounter dates: `care_start_date + relativedelta(months=month_offset)`
2. Create Encounter first, then reference it in all observations/procedures via `encounter: {"reference": f"Encounter/{enc_id}"}`
3. Use `effectiveDateTime` on Observations (not `issued`)
4. Observations within the same encounter share `encounter` reference
5. MedicationRequest `authoredOn` = encounter date; `status = "stopped"` for MedicationAction.action == "stop"
6. Set Encounter `period.start` = encounter date, `period.end` = same day (outpatient) or +3 days (inpatient)
7. Order resources in output: Patient → Practitioner → Encounter → Observation → Condition → Procedure → MedicationRequest (within each encounter group)
