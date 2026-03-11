DIAGNOSTIC REPORT REALISM:
- Status: registered, partial, preliminary, final, amended, corrected, appended, cancelled,
  entered-in-error.
- Categories: LAB (laboratory), RAD (radiology), PAT (pathology), CRD (cardiology).
- Include DiagnosticReport.result[] referencing Observation resources.
- For pathology: include conclusion and conclusionCode.
- For radiology: include presentedForm (narrative report text as attachment).
- Use effectiveDateTime or effectivePeriod for specimen collection timing.

DOCUMENT REFERENCE REALISM:
- Types (LOINC): 34133-9 (Summary of episode), 18842-5 (Discharge summary),
  11488-4 (Consultation note), 11506-3 (Progress note), 28570-0 (Procedure note),
  57133-1 (Referral note), 34117-2 (History and physical), 11504-8 (Surgical op note).
- Status: current, superseded, entered-in-error.
- Content: Include content[].attachment with contentType (application/pdf, text/plain),
  title, and creation date. Use data (base64) or url.
- Context: Link to encounter, period, facilityType, practiceSetting.

