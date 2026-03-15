CREATION ORDER — always create resources in dependency order:
  1. Organization, Practitioner, Location  (standalone)
  2. PractitionerRole (references Practitioner + Organization + Location)
  3. Patient (may reference Organization)
  4. Coverage (references Patient + Organization)
  5. Encounter (references Patient + Practitioner + Location)
  6. Condition, Observation, Procedure, (reference Patient + Encounter + Practitioner)
     MedicationRequest, DiagnosticReport,
     AllergyIntolerance, Immunization
  7. CarePlan, Goal, ServiceRequest        (reference Patient + Conditions)
  8. DocumentReference                     (references Patient + Encounter)
  9. FamilyMemberHistory (references Patient)
 10. Claim (references Patient + Coverage + Encounter + Practitioner)
 11. ClaimResponse                         (references Claim)
 12. ExplanationOfBenefit (references Patient + Coverage + Claim + Practitioner)
 13. Provenance (references any target resource — create LAST)

