Generate Python code to create FHIR $fhir_version resources.

Requirement: $requirement

$fhir_imports

FHIR SPEC (fields with types — see DATA TYPE FORMAT RULES at top):
$fhir_spec

⚠️  ALWAYS create a dt_iso() helper function in your code to ensure DateTime/Instant fields
    have timezone information. The example below demonstrates this pattern — copy it exactly.

EXAMPLE (for reference — shows key patterns: timezone-aware datetimes, Period, references):
```python
$example_imports
from uuid import uuid4
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from faker import Faker
import random

def generate_resources() -> list[dict]:
    resources = []
    fake = Faker()

    # Helper: always return timezone-aware ISO strings for DateTime/Instant fields.
    def dt_iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    patient_id = str(uuid4())
    patient = Patient(
        id=patient_id,
        name=[{"given": [fake.first_name()], "family": fake.last_name()}],
        gender=random.choice(["male", "female"]),
        birthDate=date(random.randint(1950, 2000), random.randint(1, 12), random.randint(1, 28)).isoformat(),
    )
    resources.append(patient.model_dump(exclude_none=True, mode='json'))

    # Encounter with Period (DateTime fields — MUST have timezone)
    enc_id = str(uuid4())
    start = datetime.now(timezone.utc) - timedelta(days=random.randint(7, 90))
    end = start + timedelta(hours=1)
    encounter = Encounter(
        id=enc_id,
        status="finished",
        class_fhir=Coding(system="http://terminology.hl7.org/CodeSystem/v3-ActCode", code="AMB"),
        subject=Reference(reference=f"Patient/{patient_id}"),
        period=Period(start=dt_iso(start), end=dt_iso(end)),
    )
    resources.append(encounter.model_dump(exclude_none=True, mode='json'))

    # Condition referencing Patient and Encounter
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
        subject=Reference(reference=f"Patient/{patient_id}"),
        encounter=Reference(reference=f"Encounter/{enc_id}"),
        code=CodeableConcept(coding=[Coding(
            system="http://hl7.org/fhir/sid/icd-10-cm",
            code="E11.9", display="Type 2 diabetes mellitus",
        )]),
        onsetDateTime=date(2018, 6, 15).isoformat(),  # date-only DateTime is valid
    )
    resources.append(condition.model_dump(exclude_none=True, mode='json'))

    return resources
```

Now generate code for: $requirement
