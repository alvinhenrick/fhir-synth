# Comorbidity & Multi-Condition Realism

Reflect realistic disease clustering — generate patients with co-occurring conditions (not random independent conditions).

## Common Clusters

| Cluster | Conditions (ICD-10) |
|---------|-------------------|
| Metabolic syndrome | E11.9 T2DM + I10 HTN + E78.5 Hyperlipidemia + E66.01 Obesity |
| Cardiovascular cascade | I10 HTN → I25.10 CAD → I50.9 CHF |
| CKD progression | N18.1→N18.5 staged CKD, often with I10 HTN and E11.9 T2DM |
| COPD + comorbidities | J44.1 COPD + J18.9 Pneumonia + F17.210 Nicotine dependence |
| Mental health | F32.1 Depression + F41.1 GAD (frequently co-occurring) |
| Chronic pain | M54.5 Low back pain + G89.29 Chronic pain + F11.20 Opioid use disorder |
| Geriatric syndromes | Dementia (F03.90) + falls (W19) + incontinence (R32) + frailty |
| Pediatric | J45.20 Asthma + J30.9 Allergic rhinitis + L20.9 Atopic dermatitis |

## Clinical Status Fields

- Vary **severity**: Use `Condition.severity` (mild, moderate, severe) and `clinicalStatus` (active, recurrence, relapse, inactive, remission, resolved).
- Include `verificationStatus`: confirmed, unconfirmed, provisional, differential, entered-in-error.
- **Onset**: Use `onsetDateTime`, `onsetAge`, `onsetPeriod`, or `onsetString` as appropriate. Chronic conditions should have onset years before encounter date.
- **Abatement**: Resolved conditions should have `abatementDateTime` or `abatementString`.

