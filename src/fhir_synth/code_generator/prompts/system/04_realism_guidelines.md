REALISM GUIDELINES — use the Faker library for realistic demographics:
- ALWAYS use Faker: from faker import Faker; fake = Faker()
- Patient names: fake.first_name_male() / fake.first_name_female() / fake.last_name()
- Birth dates: fake.date_of_birth(minimum_age=0, maximum_age=90).isoformat()
- Addresses: fake.street_address(), fake.city(), fake.state_abbr(), fake.zipcode()
- Phone: fake.phone_number()
- Identifiers: fake.bothify('MRN-####-????') for MRNs
- Vary gender (male/female/other) and match names to gender
- Conditions: use real ICD-10-CM + SNOMED CT dual codes (see TERMINOLOGY section for system URIs).
- Observations: use real LOINC codes with valueQuantity (unit from UCUM).
- MedicationRequests: use real RxNorm codes. Include dosageInstruction with timing and route.
- Encounters: use proper class codes (AMB, IMP, EMER), realistic periods.
- Procedures: use SNOMED CT or CPT codes with body site.
- Claims/EOB: use CPT (professional), revenue codes (institutional), NDC (pharmacy).
- Bundles: link all resources via proper references (Patient/uuid).
- Metadata: when security/tags/profiles are requested, use FHIR Meta model:
  * Security labels: http://terminology.hl7.org/CodeSystem/v3-Confidentiality (N=Normal, R=Restricted, V=Very restricted)
  * Tags: custom systems like http://example.org/tags with workflow codes
  * Profiles: US Core profiles (http://hl7.org/fhir/us/core/StructureDefinition/us-core-*)
  * Source: system URIs like http://example.org/fhir-system



