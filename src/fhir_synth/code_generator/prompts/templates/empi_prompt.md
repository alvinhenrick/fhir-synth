EMPI LINKAGE REQUIREMENTS:
- Generate $persons Person resource(s), each linked to one Patient per system.
- Systems: $systems
- $orgs_hint
- Use Person.link[].target to reference each Patient.
- Each Patient must have identifier with system "urn:emr:{system_id}" and managingOrganization.
- Patient demographics must be identical across linked records (same real person).
- Follow the EMPI patterns described in the system prompt.

$user_prompt
