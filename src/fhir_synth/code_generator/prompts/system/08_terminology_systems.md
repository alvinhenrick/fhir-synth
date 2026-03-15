TERMINOLOGY & CODE SYSTEMS — use these EXACT system URIs when coding resources.
All codes MUST come from real, published terminologies — never invent codes.

DIAGNOSIS CODES:
- ICD-10-CM:  system = "http://hl7.org/fhir/sid/icd-10-cm"
  Spec: https://www.cms.gov/Medicare/Coding/ICD10
  Format: letter + digits with dot (e.g., E11.9, I10, J44.1, M54.5, F32.1)
- SNOMED CT:  system = "http://snomed.info/sct"
  Browser: https://browser.ihtsdotools.org
  Format: numeric (e.g., 44054006 Diabetes, 38341003 Hypertension)
  Use for: conditions, procedures, body sites, findings, clinical status
- ICD-10-PCS (inpatient procedures): system = "http://www.cms.gov/Medicare/Coding/ICD10"

LAB & OBSERVATION CODES:
- LOINC:  system = "http://loinc.org"
  Search: https://loinc.org/search/
  Format: numeric with dash (e.g., 4548-4 HbA1c, 2339-0 Glucose, 8867-4 Heart rate)
  Use for: all Observation.code, DiagnosticReport.code, vital signs, lab panels

MEDICATION CODES:
- RxNorm:  system = "http://www.nlm.nih.gov/research/umls/rxnorm"
  Browser: https://mor.nlm.nih.gov/RxNav/
  Format: numeric concept ID (e.g., 6809 Metformin, 29046 Lisinopril, 83367 Atorvastatin)
  Use for: MedicationRequest.medicationCodeableConcept, Medication.code
- NDC (National Drug Code): system = "http://hl7.org/fhir/sid/ndc"
  Format: 10-11 digit (e.g., 00093-7214-01 Metformin 500mg tablet)
  Use for: Claim.item.productOrService (pharmacy claims), Medication.code

PROCEDURE CODES:
- CPT:  system = "http://www.ama-assn.org/go/cpt"
  Format: 5-digit (e.g., 99213 office visit, 27447 knee replacement)
  Use for: Procedure.code, Claim.item.productOrService (professional claims)
- HCPCS:  system = "https://www.cms.gov/Medicare/Coding/HCPCSReleaseCodeSets"
  Format: letter + 4 digits (e.g., J0171 Adrenalin injection)
  Use for: durable medical equipment, drugs administered in office
- CDT (dental):  system = "http://www.ada.org/cdt"
  Format: D + 4 digits (e.g., D0120 periodic oral evaluation)

VACCINE CODES:
- CVX:  system = "http://hl7.org/fhir/sid/cvx"
  Reference: https://www2a.cdc.gov/vaccines/iis/iisstandards/vaccines.asp?rpt=cvx
  Format: numeric (e.g., 208 COVID-19 mRNA, 140 Influenza, 03 MMR)
- MVX (manufacturer):  system = "http://hl7.org/fhir/sid/mvx"

IDENTIFIER SYSTEMS:
- NPI:  system = "http://hl7.org/fhir/sid/us-npi"  (10-digit, Practitioners + Organizations)
- SSN:  system = "http://hl7.org/fhir/sid/us-ssn"  (use fake SSNs only)
- MRN:  system = "http://hospital.example.org/mrn"  (facility-specific)
- Driver License:  system = "urn:oid:2.16.840.1.113883.4.3.{state_fips}"
- Member ID:  system = "http://insurance.example.org/member-id"

CLINICAL STATUS / CATEGORY SYSTEMS:
- Condition clinical status:  "http://terminology.hl7.org/CodeSystem/condition-clinical"
  Codes: active, recurrence, relapse, inactive, remission, resolved
- Condition verification:  "http://terminology.hl7.org/CodeSystem/condition-ver-status"
  Codes: confirmed, unconfirmed, provisional, differential, refuted, entered-in-error
- Condition category:  "http://terminology.hl7.org/CodeSystem/condition-category"
  Codes: problem-list-item, encounter-diagnosis
- Observation category:  "http://terminology.hl7.org/CodeSystem/observation-category"
  Codes: vital-signs, laboratory, social-history, imaging, exam, procedure, survey
- Encounter class:  "http://terminology.hl7.org/CodeSystem/v3-ActCode"
  Codes: AMB, IMP, EMER, HH, VR, OBSENC, SS
- Adjudication:  "http://terminology.hl7.org/CodeSystem/adjudication"
  Codes: submitted, eligible, deductible, copay, benefit

UNIT SYSTEMS:
- UCUM (units of measure):  system = "http://unitsofmeasure.org"
  Common: mg/dL, mmol/L, %, mmHg, /min, kg, cm, Cel, [pH], 10*3/uL, g/dL
  Reference: https://ucum.org/ucum

FHIR SPECIFICATION REFERENCES:
- FHIR R4B:  https://hl7.org/fhir/R4B/
- US Core IG (profiles):  https://www.hl7.org/fhir/us/core/
- FHIR Terminology:  https://terminology.hl7.org/
- Value Sets:  https://hl7.org/fhir/R4B/terminologies-valuesets.html
- Resource list:  https://hl7.org/fhir/R4B/resourcelist.html

UMLS / NLM RESOURCES:
- UMLS Metathesaurus (cross-maps ICD-10 ↔ SNOMED ↔ RxNorm):
  https://www.nlm.nih.gov/research/umls/
- RxNav (drug lookup):  https://mor.nlm.nih.gov/RxNav/
- VSAC (value sets):  https://vsac.nlm.nih.gov/



