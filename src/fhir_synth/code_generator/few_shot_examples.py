"""Few-shot examples for DSPy code generation.

Each example is a complete (requirement → code) pair that DSPy uses
as demonstrations. These are loaded by the DSPy generator to provide
few-shot context — this is DSPy's primary strength over raw prompting.

Add new examples as you find successful generations to improve accuracy.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Example 1: Simple diabetic patients with observations
# ---------------------------------------------------------------------------

EXAMPLE_DIABETIC = {
    "requirement": "Generate 3 diabetic patients with HbA1c observations",
    "code": """\
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.quantity import Quantity
from uuid import uuid4
from decimal import Decimal
from faker import Faker
import random

fake = Faker()

def generate_resources() -> list[dict]:
    resources = []
    hba1c_values = [Decimal("6.8"), Decimal("8.2"), Decimal("11.5")]

    for i in range(3):
        patient_id = str(uuid4())
        gender = random.choice(["male", "female"])
        patient = Patient(
            id=patient_id,
            name=[{
                "given": [fake.first_name_male() if gender == "male" else fake.first_name_female()],
                "family": fake.last_name(),
            }],
            gender=gender,
            birthDate=fake.date_of_birth(minimum_age=30, maximum_age=80).isoformat(),
        )
        resources.append(patient.model_dump(exclude_none=True))

        condition = Condition(
            id=str(uuid4()),
            clinicalStatus=CodeableConcept(coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                code="active", display="Active",
            )]),
            verificationStatus=CodeableConcept(coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
                code="confirmed", display="Confirmed",
            )]),
            code=CodeableConcept(coding=[Coding(
                system="http://hl7.org/fhir/sid/icd-10-cm",
                code="E11.9", display="Type 2 diabetes mellitus without complications",
            )]),
            subject=Reference(reference=f"Patient/{patient_id}"),
        )
        resources.append(condition.model_dump(exclude_none=True))

        observation = Observation(
            id=str(uuid4()),
            status="final",
            code=CodeableConcept(coding=[Coding(
                system="http://loinc.org", code="4548-4",
                display="Hemoglobin A1c/Hemoglobin.total in Blood",
            )]),
            subject=Reference(reference=f"Patient/{patient_id}"),
            valueQuantity=Quantity(
                value=hba1c_values[i], unit="%",
                system="http://unitsofmeasure.org", code="%",
            ),
        )
        resources.append(observation.model_dump(exclude_none=True))

    return resources
""",
}

# ---------------------------------------------------------------------------
# Example 2: Patient with encounter, vitals, and medication
# ---------------------------------------------------------------------------

EXAMPLE_ENCOUNTER_VITALS = {
    "requirement": "Generate 2 patients with office visit encounters, blood pressure observations, and medication requests",
    "code": """\
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.medicationrequest import MedicationRequest
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.period import Period
from uuid import uuid4
from decimal import Decimal
from datetime import datetime, timezone
from faker import Faker
import random

fake = Faker()

def generate_resources() -> list[dict]:
    resources = []

    for _ in range(2):
        patient_id = str(uuid4())
        gender = random.choice(["male", "female"])
        patient = Patient(
            id=patient_id,
            name=[{
                "given": [fake.first_name_male() if gender == "male" else fake.first_name_female()],
                "family": fake.last_name(),
            }],
            gender=gender,
            birthDate=fake.date_of_birth(minimum_age=25, maximum_age=75).isoformat(),
        )
        resources.append(patient.model_dump(exclude_none=True))

        encounter_id = str(uuid4())
        encounter = Encounter(
            id=encounter_id,
            status="finished",
            **{"class": Coding(
                system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                code="AMB", display="ambulatory",
            )},
            type=[CodeableConcept(coding=[Coding(
                system="http://snomed.info/sct",
                code="308335008", display="Patient encounter procedure",
            )])],
            subject=Reference(reference=f"Patient/{patient_id}"),
            period=Period(
                start=datetime.now(timezone.utc).isoformat(),
                end=datetime.now(timezone.utc).isoformat(),
            ),
        )
        resources.append(encounter.model_dump(exclude_none=True))

        systolic = random.randint(110, 160)
        diastolic = random.randint(60, 100)
        bp = Observation(
            id=str(uuid4()),
            status="final",
            category=[CodeableConcept(coding=[Coding(
                system="http://terminology.hl7.org/CodeSystem/observation-category",
                code="vital-signs", display="Vital Signs",
            )])],
            code=CodeableConcept(coding=[Coding(
                system="http://loinc.org", code="85354-9",
                display="Blood pressure panel",
            )]),
            subject=Reference(reference=f"Patient/{patient_id}"),
            encounter=Reference(reference=f"Encounter/{encounter_id}"),
            component=[
                {
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}]},
                    "valueQuantity": {"value": Decimal(systolic), "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"},
                },
                {
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}]},
                    "valueQuantity": {"value": Decimal(diastolic), "unit": "mmHg", "system": "http://unitsofmeasure.org", "code": "mm[Hg]"},
                },
            ],
        )
        resources.append(bp.model_dump(exclude_none=True))

        med = MedicationRequest(
            id=str(uuid4()),
            status="active",
            intent="order",
            medicationCodeableConcept=CodeableConcept(coding=[Coding(
                system="http://www.nlm.nih.gov/research/umls/rxnorm",
                code="29046", display="Lisinopril 10 MG Oral Tablet",
            )]),
            subject=Reference(reference=f"Patient/{patient_id}"),
            encounter=Reference(reference=f"Encounter/{encounter_id}"),
        )
        resources.append(med.model_dump(exclude_none=True))

    return resources
""",
}

# ---------------------------------------------------------------------------
# Example 3: Minimal — just patients (shows simplest correct pattern)
# ---------------------------------------------------------------------------

EXAMPLE_SIMPLE_PATIENTS = {
    "requirement": "Generate 5 patients with diverse demographics",
    "code": """\
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.extension import Extension
from uuid import uuid4
from faker import Faker
import random

fake = Faker()

def generate_resources() -> list[dict]:
    resources = []
    genders = ["male", "female", "other"]

    for _ in range(5):
        patient_id = str(uuid4())
        gender = random.choice(genders)
        patient = Patient(
            id=patient_id,
            name=[{
                "given": [fake.first_name()],
                "family": fake.last_name(),
            }],
            gender=gender,
            birthDate=fake.date_of_birth(minimum_age=0, maximum_age=90).isoformat(),
            address=[{
                "use": "home",
                "city": fake.city(),
                "state": fake.state_abbr(),
                "postalCode": fake.zipcode(),
            }],
            telecom=[{"system": "phone", "value": fake.phone_number()}],
        )
        resources.append(patient.model_dump(exclude_none=True))

    return resources
""",
}


# ---------------------------------------------------------------------------
# All examples — add new ones here
# ---------------------------------------------------------------------------

ALL_EXAMPLES: list[dict[str, str]] = [
    EXAMPLE_SIMPLE_PATIENTS,
    EXAMPLE_DIABETIC,
    EXAMPLE_ENCOUNTER_VITALS,
]
