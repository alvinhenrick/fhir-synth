EMPI (Enterprise Master Patient Index) — generate cross-system patient linkage:
- Create Person resources that link to one Patient per source system via Person.link[].target.
- Each Patient MUST have a unique identifier with system = "urn:emr:{system_id}".
- Each Patient MUST have managingOrganization referencing their source Organization.
- Create Organization resources for each EMR system with identifier system = "urn:emr".
- Person.link[] entries use assurance = "level4" (highest linkage confidence).
- Patient demographics (name, gender, birthDate) should be IDENTICAL across linked records
  (they represent the same real person in different systems).
- Patient IDs should follow the pattern: "{system}-patient-{person_number}"
  (e.g. "emr1-patient-1", "emr2-patient-1" for the same person).
- Person IDs should follow the pattern: "person-{number}".
- Organization IDs should follow the pattern: "org-{system}".
- Include Patient.identifier with MRN per system (different MRN values per system).
- CREATION ORDER for EMPI: Organization → Patient → Person (dependency order).
- If clinical resources (Conditions, Observations, etc.) are also requested,
  attach them to ONE of the Patient records per person (the "primary" system),
  not duplicated across all system Patients.
