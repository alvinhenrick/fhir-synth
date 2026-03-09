Generate Python code to create FHIR R4B resources.

Requirement: $requirement

$fhir_imports

FHIR SPEC (required, reference, and optional fields for common resource types):
$fhir_spec

Remember:
- def generate_resources() -> list[dict]:
- import from fhir.resources.R4B (e.g. from fhir.resources.R4B.patient import Patient)
- .model_dump(exclude_none=True) on every resource
- uuid4 for IDs, Decimal for numeric values
- real clinical codes (ICD-10, LOINC, RxNorm, SNOMED)
- diverse, realistic data with patient variation (age groups, gender, race, language, insurance)
- realistic comorbidity clusters (not random independent conditions)
- vital signs with proper components (e.g. BP has systolic + diastolic components)
- lab results with referenceRange and interpretation codes
- include SDOH observations when generating comprehensive patient data
- allergy and immunization records with proper code systems (SNOMED, CVX)

EXAMPLE (for reference - adapt to your requirement):
```python
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.extension import Extension
from uuid import uuid4
from datetime import date
from decimal import Decimal
import random

def generate_resources() -> list[dict]:
    resources = []

    # Generate patient with US Core extensions for race/ethnicity
    patient_id = str(uuid4())
    gender = random.choice(["male", "female", "other"])
    patient = Patient(
        id=patient_id,
        name=[{"given": ["John"], "family": "Doe"}],
        gender=gender,
        birthDate="1970-01-01",
        extension=[
            Extension(
                url="http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                extension=[
                    Extension(url="ombCategory", valueCoding=Coding(
                        system="urn:oid:2.16.840.1.113883.6.238",
                        code="2106-3", display="White"
                    )),
                    Extension(url="text", valueString="White")
                ]
            )
        ],
        communication=[{
            "language": {"coding": [{"system": "urn:ietf:bcp:47", "code": "en"}]},
            "preferred": True
        }]
    )
    resources.append(patient.model_dump(exclude_none=True))

    # Generate related condition with severity and clinical status
    condition = Condition(
        id=str(uuid4()),
        clinicalStatus=CodeableConcept(
            coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                code="active", display="Active"
            )]
        ),
        verificationStatus=CodeableConcept(
            coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
                code="confirmed", display="Confirmed"
            )]
        ),
        severity=CodeableConcept(
            coding=[Coding(
                system="http://snomed.info/sct",
                code="24484000", display="Severe"
            )]
        ),
        subject=Reference(reference=f"Patient/{patient_id}"),
        code=CodeableConcept(
            coding=[Coding(
                system="http://hl7.org/fhir/sid/icd-10-cm",
                code="E11.9",
                display="Type 2 diabetes mellitus"
            )]
        ),
        onsetDateTime="2018-06-15"
    )
    resources.append(condition.model_dump(exclude_none=True))

    return resources
```

Now generate code for: $requirement

