EMPI (Enterprise Master Patient Index) LINKAGE REQUIREMENTS:
- Generate $persons Person resource(s), each linked to one Patient per source system.
- Systems: $systems
- $orgs_hint
- Create Person resources that link to one Patient per source system via Person.link[].target.
- Each Patient MUST have a unique identifier with system = "urn:emr:{system_id}".
- Each Patient MUST have managingOrganization referencing their source Organization.
- Person.link[] entries use assurance = "level4" (highest linkage confidence).
- Patient demographics (name, gender, birthDate) MUST be IDENTICAL across linked records
  (they represent the same real person in different systems).
- Include Patient.identifier with MRN per system (different MRN values per system).
- CREATION ORDER for EMPI: Organization → Patient → Person (dependency order).
- If clinical resources (Conditions, Observations, etc.) are also requested,
  attach them to ONE of the Patient records per person (the "primary" system),
  not duplicated across all system Patients.

$user_prompt
