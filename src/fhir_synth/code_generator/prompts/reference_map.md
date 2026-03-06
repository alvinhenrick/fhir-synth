# Reference Field Map

Use these exact field names when linking resources:

| Field | Reference Target |
|-------|-----------------|
| `Encounter.subject` | `Reference("Patient/{id}")` |
| `Encounter.participant.individual` | `Reference("Practitioner/{id}")` |
| `Encounter.serviceProvider` | `Reference("Organization/{id}")` |
| `Condition.subject` | `Reference("Patient/{id}")` |
| `Condition.encounter` | `Reference("Encounter/{id}")` |
| `Observation.subject` | `Reference("Patient/{id}")` |
| `Observation.encounter` | `Reference("Encounter/{id}")` |
| `Procedure.subject` | `Reference("Patient/{id}")` |
| `Procedure.encounter` | `Reference("Encounter/{id}")` |
| `MedicationRequest.subject` | `Reference("Patient/{id}")` |
| `MedicationRequest.encounter` | `Reference("Encounter/{id}")` |
| `MedicationRequest.requester` | `Reference("Practitioner/{id}")` |
| `DiagnosticReport.subject` | `Reference("Patient/{id}")` |
| `DiagnosticReport.encounter` | `Reference("Encounter/{id}")` |
| `DocumentReference.subject` | `Reference("Patient/{id}")` |
| `Immunization.patient` | `Reference("Patient/{id}")` |
| `Immunization.encounter` | `Reference("Encounter/{id}")` |
| `AllergyIntolerance.patient` | `Reference("Patient/{id}")` |
| `CarePlan.subject` | `Reference("Patient/{id}")` |
| `ServiceRequest.subject` | `Reference("Patient/{id}")` |
| `Person.link[].target` | `Reference("Patient/{id}")` (EMPI linkage) |
| `Coverage.beneficiary` | `Reference("Patient/{id}")` |
| `Coverage.payor` | `Reference("Organization/{id}")` |
| `Goal.subject` | `Reference("Patient/{id}")` |
| `Provenance.target` | `Reference("{ResourceType}/{id}")` |
| `Provenance.agent.who` | `Reference("Practitioner/{id}")` |
| `FamilyMemberHistory.patient` | `Reference("Patient/{id}")` |

# Creation Order

Always create resources in dependency order:

1. Organization, Practitioner, Location (standalone)
2. Patient (may reference Organization)
3. Person (links to Patient for EMPI)
4. Coverage (references Patient + Organization)
5. Encounter (references Patient)
6. Condition, Observation, Procedure, MedicationRequest, DiagnosticReport, AllergyIntolerance, Immunization (reference Patient + Encounter)
7. CarePlan, Goal, ServiceRequest (reference Patient + Conditions)
8. DocumentReference (references Patient + Encounter)
9. FamilyMemberHistory (references Patient)
10. Provenance (references any target resource)

