# Coverage & Insurance

Model payer diversity.

## Coverage Resource
Include `subscriber`, `beneficiary`, `payor` references.

## Payer Types
Medicare (Part A, B, C, D), Medicaid, Commercial (BCBS, Aetna, UHC, Cigna), Tricare, VA, Self-pay/uninsured, Workers' Comp.

## Class
group, plan, subplan, class, subclass, sequence.

## Type Codes
System: `http://terminology.hl7.org/CodeSystem/v3-ActCode`

| Code | Meaning |
|------|---------|
| EHCPOL | Employee healthcare |
| PUBLICPOL | Public policy |
| SUBSIDIZ | Subsidized |
| MANDPOL | Mandatory policy |

## Period
Coverage start/end dates, with some patients having gaps in coverage. Include patients with multiple coverages (primary/secondary coordination).

