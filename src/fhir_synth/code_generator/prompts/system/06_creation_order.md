CREATION ORDER — always create resources in dependency order:
  1. Organization, Practitioner, Location  (standalone)
  2. Patient                               (may reference Organization)
  3. Coverage                              (references Patient + Organization)
  4. Encounter                             (references Patient)
  5. Condition, Observation, Procedure,    (reference Patient + Encounter)
     MedicationRequest, DiagnosticReport,
     AllergyIntolerance, Immunization
  6. CarePlan, Goal, ServiceRequest        (reference Patient + Conditions)
  7. DocumentReference                     (references Patient + Encounter)
  8. FamilyMemberHistory                   (references Patient)
  9. Provenance                            (references any target resource)

