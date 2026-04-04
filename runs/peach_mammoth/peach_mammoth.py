from datetime import datetime, timezone, date
from decimal import Decimal
from uuid import uuid4
from faker import Faker

from fhir.resources.R4B.meta import Meta
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.address import Address
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.timing import Timing, TimingRepeat
from fhir.resources.R4B.dosage import Dosage
from fhir.resources.R4B.quantity import Quantity

from fhir.resources.R4B.practitioner import Practitioner
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.medicationrequest import MedicationRequest
from fhir.resources.R4B.allergyintolerance import AllergyIntolerance


def generate_resources() -> list[dict]:
    fake = Faker()

    def dt_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def make_meta(profile_url: str | None = None) -> Meta:
        security = [
            Coding(system="https://www.icanbwell.com/access", code="bwell", display="bwell"),
            Coding(system="https://www.icanbwell.com/owner", code="bwell", display="bwell"),
        ]
        return Meta(
            security=security,
            profile=[profile_url] if profile_url else None,
            source="https://github.com/alvinhenrick/fhir-synth.git",
        )

    resources: list[dict] = []

    # Practitioner
    practitioner_id = str(uuid4())
    practitioner = Practitioner(
        id=practitioner_id,
        meta=make_meta(),
        active=True,
        name=[
            HumanName(
                family="Smith",
                given=["Dr.", "Smith"]
            )
        ],
        gender="male",
        telecom=[ContactPoint(system="phone", value=fake.phone_number(), use="work")]
    )
    resources.append(practitioner.model_dump(exclude_none=True, mode="json"))

    # Patient
    patient_id = str(uuid4())
    # Set birth date to align with age 58
    today = date.today()
    birth_year = today.year - 58
    birth_date = date(birth_year, fake.random_int(1, 12), fake.random_int(1, 28)).isoformat()

    patient = Patient(
        id=patient_id,
        meta=make_meta("http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"),
        active=True,
        name=[
            HumanName(
                family=fake.last_name(),
                given=[fake.first_name_female()]
            )
        ],
        gender="female",
        birthDate=birth_date,
        identifier=[
            Identifier(
                system="http://hospital.example.org/mrn",
                value=fake.bothify("MRN-####-????")
            )
        ],
        address=[
            Address(
                line=[fake.street_address()],
                city=fake.city(),
                state=fake.state_abbr(),
                postalCode=fake.zipcode(),
                country="US"
            )
        ],
        telecom=[ContactPoint(system="phone", value=fake.phone_number(), use="home")]
    )
    resources.append(patient.model_dump(exclude_none=True, mode="json"))

    # Encounter
    encounter_id = str(uuid4())
    encounter = Encounter(
        id=encounter_id,
        meta=make_meta(),
        status="finished",
        class_fhir=Coding(system="http://terminology.hl7.org/CodeSystem/v3-ActCode", code="AMB", display="ambulatory"),
        type=[CodeableConcept(text="oncology consultation")],
        subject=Reference(reference=f"Patient/{patient_id}"),
        participant=[
            {
                "individual": Reference(reference=f"Practitioner/{practitioner_id}")
            }
        ],
        period=Period(start=dt_iso(), end=dt_iso())
    )
    resources.append(encounter.model_dump(exclude_none=True, mode="json"))

    # Conditions
    conditions_data = [
        {
            "system": "http://snomed.info/sct",
            "code": "363443007",
            "display": "Malignant neoplasm of ovary",
            "onset": "diagnosed 3 months ago",
            "severity": "severe",
        },
        {
            "system": "http://hl7.org/fhir/sid/icd-10-cm",
            "code": "C56.9",
            "display": "Malignant neoplasm of ovary",
            "onset": "diagnosed 3 months ago",
            "severity": "severe",
        },
        {
            "system": "http://snomed.info/sct",
            "code": "38341003",
            "display": "Hypertension",
            "onset": "10 years ago",
            "severity": "moderate",
        },
        {
            "system": "http://snomed.info/sct",
            "code": "40930008",
            "display": "Hypothyroidism",
            "onset": "5 years ago",
            "severity": "mild",
        },
    ]

    for c in conditions_data:
        condition = Condition(
            id=str(uuid4()),
            meta=make_meta(),
            clinicalStatus=CodeableConcept(
                coding=[Coding(system="http://terminology.hl7.org/CodeSystem/condition-clinical", code="active", display="Active")]
            ),
            verificationStatus=CodeableConcept(
                coding=[Coding(system="http://terminology.hl7.org/CodeSystem/condition-ver-status", code="confirmed", display="Confirmed")]
            ),
            category=[CodeableConcept(
                coding=[Coding(system="http://terminology.hl7.org/CodeSystem/condition-category", code="problem-list-item", display="Problem List Item")]
            )],
            severity=CodeableConcept(text=c["severity"]),
            code=CodeableConcept(coding=[Coding(system=c["system"], code=c["code"], display=c["display"])]),
            subject=Reference(reference=f"Patient/{patient_id}"),
            encounter=Reference(reference=f"Encounter/{encounter_id}"),
            recorder=Reference(reference=f"Practitioner/{practitioner_id}"),
            onsetString=c["onset"],
            recordedDate=dt_iso()
        )
        resources.append(condition.model_dump(exclude_none=True, mode="json"))

    # MedicationRequests
    meds = [
        {"rxnorm": "40048", "display": "Carboplatin IV", "dose": "AUC 5", "frequency": "every 21 days"},
        {"rxnorm": "56946", "display": "Paclitaxel IV", "dose": "175 mg/m2", "frequency": "every 21 days"},
        {"rxnorm": "26225", "display": "Ondansetron", "dose": "8 mg", "frequency": "pre-chemo"},
        {"rxnorm": "3264", "display": "Dexamethasone", "dose": "12 mg", "frequency": "pre-chemo"},
        {"rxnorm": "3498", "display": "Diphenhydramine", "dose": "25 mg", "frequency": "pre-chemo"},
    ]

    for m in meds:
        if "21 days" in m["frequency"]:
            timing = Timing(
                repeat=TimingRepeat(
                    frequency=1,
                    period=Decimal(21),
                    periodUnit="d"
                )
            )
        else:
            timing = Timing(
                repeat=TimingRepeat(
                    frequency=1,
                    period=Decimal(1),
                    periodUnit="d"
                )
            )

        dosage = Dosage(
            text=f"{m['display']} {m['dose']} {m['frequency']}",
            timing=timing
        )

        med_request = MedicationRequest(
            id=str(uuid4()),
            meta=make_meta(),
            status="active",
            intent="order",
            medicationCodeableConcept=CodeableConcept(
                coding=[Coding(system="http://www.nlm.nih.gov/research/umls/rxnorm", code=m["rxnorm"], display=m["display"])]
            ),
            subject=Reference(reference=f"Patient/{patient_id}"),
            encounter=Reference(reference=f"Encounter/{encounter_id}"),
            requester=Reference(reference=f"Practitioner/{practitioner_id}"),
            authoredOn=dt_iso(),
            dosageInstruction=[dosage],
            reportedBoolean=False
        )
        resources.append(med_request.model_dump(exclude_none=True, mode="json"))

    # AllergyIntolerance
    allergy = AllergyIntolerance(
        id=str(uuid4()),
        meta=make_meta(),
        patient=Reference(reference=f"Patient/{patient_id}"),
        clinicalStatus=CodeableConcept(
            coding=[Coding(system="http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical", code="active", display="Active")]
        ),
        category=["medication"],
        criticality="high",
        code=CodeableConcept(
            coding=[Coding(system="http://snomed.info/sct", code="416098002", display="Drug allergy to sulfonamide")]
        ),
        onsetString="unknown"
    )
    resources.append(allergy.model_dump(exclude_none=True, mode="json"))

    return resources