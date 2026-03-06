# Provenance & Data Quality

## Provenance
Track data origin:
- Include Provenance resources for audit trail.
- **Agent**: who created/modified the data (Practitioner, Organization, Device, Patient).
- **Activity**: create, update, delete (`http://terminology.hl7.org/CodeSystem/v3-DataOperation`).
- **Recorded**: timestamp of the provenance event.
- **Target**: reference to the resource being tracked.

## Data Quality Variation
Reflect real EHR messiness:
- Include some resources with missing optional fields (sparse records).
- Vary data completeness: some patients fully documented, others sparse.
- Include some conditions with `verificationStatus` = `"unconfirmed"` or `"provisional"`.
- Include some encounters with `status` = `"cancelled"` or `"entered-in-error"`.
- Include some observations with `dataAbsentReason` (masked, not-asked, unknown, not-performed). Use `http://terminology.hl7.org/CodeSystem/data-absent-reason`.

