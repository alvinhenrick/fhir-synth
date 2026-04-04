from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from dateutil.relativedelta import relativedelta
from faker import Faker

from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.encounter import Encounter
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.medicationrequest import MedicationRequest
from fhir.resources.R4B.allergyintolerance import AllergyIntolerance

from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.address import Address
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.meta import Meta
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.dosage import Dosage, DosageDoseAndRate
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.timing import Timing, TimingRepeat


def generate_resources() -> list[dict]:
    fake = Faker()
    resources = []

    def dt_iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def meta_common(with_profile: bool = False) -> Meta:
        security = [
            Coding(system="https://www.icanbwell.com/access", code="bwell", display="bwell"),
            Coding(system="https://www.icanbwell.com/owner", code="bwell", display="bwell"),
        ]
        profile = ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"] if with_profile else None
        return Meta(security=security, source="https://github.com/alvinhenrick/fhir-synth.git", profile=profile)

    # Patient
    patient_id = str(uuid4())
    birth_date = (date.today() - relativedelta(years=58)).isoformat()

    patient = Patient(
        id=patient_id,
        meta=meta_common(with_profile=True),
        active=True,
        gender="female",
        name=[HumanName(use="official", family=fake.last_name(), given=[fake.first_name_female()])],
        birthDate=birth_date,
        identifier=[
            Identifier(system="http://hospital.example.org/mrn", value=fake.bothify("MRN-####-????"))
        ],
        address=[
            Address(
                line=[fake.street_address()],
                city=fake.city(),
                state=fake.state_abbr(),
                postalCode=fake.zipcode(),
                country="US",
            )
        ],
        telecom=[ContactPoint(system="phone", value=fake.phone_number(), use="home")],
    )
    resources.append(patient.model_dump(exclude_none=True, mode="json"))

    patient_ref = Reference(reference=f"Patient/{patient_id}")

    # Encounter
    encounter_id = str(uuid4())
    start_dt = datetime.now(timezone.utc) - timedelta(days=7)
    end_dt = start_dt + timedelta(hours=1)

    encounter = Encounter(
        id=encounter_id,
        meta=meta_common(),
        status="finished",
        class_fhir=Coding(
            system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
            code="AMB",
            display="ambulatory",
        ),
        subject=patient_ref,
        type=[CodeableConcept(text="Oncology consultation")],
        period=Period(start=dt_iso(start_dt), end=dt_iso(end_dt)),
    )
    resources.append(encounter.model_dump(exclude_none=True, mode="json"))

    encounter_ref = Reference(reference=f"Encounter/{encounter_id}")

    # Conditions
    condition_defs = [
        {
            "snomed": ("363443007", "Malignant tumor of ovary"),
            "icd10": ("C56.9", "Malignant neoplasm of ovary, unspecified"),
            "onset": "diagnosed 3 months ago",
            "severity": "severe",
        },
        {
            "snomed": ("38341003", "Hypertensive disorder, systemic arterial"),
            "icd10": ("I10", "Essential (primary) hypertension"),
            "onset": "10 years ago",
            "severity": "moderate",
        },
        {
            "snomed": ("40930008", "Hypothyroidism"),
            "icd10": ("E03.9", "Hypothyroidism, unspecified"),
            "onset": "8 years ago",
            "severity": "mild",
        },
    ]

    severity_map = {
        "mild": ("255604002", "Mild"),
        "moderate": ("6736007", "Moderate"),
        "severe": ("24484000", "Severe"),
    }

    for c in condition_defs:
        severity_code, severity_display = severity_map[c["severity"]]
        condition = Condition(
            id=str(uuid4()),
            meta=meta_common(),
            subject=patient_ref,
            encounter=encounter_ref,
            clinicalStatus=CodeableConcept(
                coding=[
                    Coding(
                        system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                        code="active",
                        display="Active",
                    )
                ]
            ),
            verificationStatus=CodeableConcept(
                coding=[
                    Coding(
                        system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        code="confirmed",
                        display="Confirmed",
                    )
                ]
            ),
            category=[
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/condition-category",
                            code="problem-list-item",
                            display="Problem List Item",
                        )
                    ]
                )
            ],
            severity=CodeableConcept(
                coding=[
                    Coding(
                        system="http://terminology.hl7.org/CodeSystem/condition-severity",
                        code=c["severity"],
                        display=c["severity"].capitalize(),
                    ),
                    Coding(system="http://snomed.info/sct", code=severity_code, display=severity_display),
                ]
            ),
            code=CodeableConcept(
                coding=[
                    Coding(system="http://snomed.info/sct", code=c["snomed"][0], display=c["snomed"][1]),
                    Coding(system="http://hl7.org/fhir/sid/icd-10-cm", code=c["icd10"][0], display=c["icd10"][1]),
                ],
                text=c["snomed"][1],
            ),
            onsetString=c["onset"],
        )
        resources.append(condition.model_dump(exclude_none=True, mode="json"))

    # MedicationRequests
    meds = [
        {"rx": "40048", "display": "Carboplatin IV", "dose": "AUC 5", "route": "IV", "frequency": "every 21 days"},
        {"rx": "56946", "display": "Paclitaxel IV", "dose": "175 mg/m2", "route": "IV", "frequency": "every 21 days"},
        {"rx": "26225", "display": "Ondansetron", "dose": "8 mg", "route": "oral", "frequency": "as needed for nausea"},
        {"rx": "29046", "display": "Lisinopril", "dose": "10 mg", "route": "oral", "frequency": "daily"},
        {"rx": "7052", "display": "Levothyroxine", "dose": "75 mcg", "route": "oral", "frequency": "daily"},
    ]

    def route_cc(route: str) -> CodeableConcept:
        if route.lower() == "iv":
            return CodeableConcept(coding=[Coding(system="http://snomed.info/sct", code="47625008", display="Intravenous route")])
        return CodeableConcept(coding=[Coding(system="http://snomed.info/sct", code="26643006", display="Oral route")])

    def dosage_for(med):
        freq = med["frequency"]
        timing = None
        as_needed = None
        if "every 21 days" in freq:
            timing = Timing(repeat=TimingRepeat(frequency=1, period=Decimal(21), periodUnit="d"))
        elif "daily" in freq:
            timing = Timing(repeat=TimingRepeat(frequency=1, period=Decimal(1), periodUnit="d"))
        elif "as needed" in freq:
            as_needed = True

        dose_quantity = None
        if med["dose"] == "AUC 5":
            dose_quantity = Quantity(value=Decimal(5), unit="AUC")
        elif "mg/m2" in med["dose"]:
            dose_quantity = Quantity(value=Decimal(175), unit="mg/m2", system="http://unitsofmeasure.org", code="mg/m2")
        elif "8 mg" in med["dose"]:
            dose_quantity = Quantity(value=Decimal(8), unit="mg", system="http://unitsofmeasure.org", code="mg")
        elif "10 mg" in med["dose"]:
            dose_quantity = Quantity(value=Decimal(10), unit="mg", system="http://unitsofmeasure.org", code="mg")
        elif "75 mcg" in med["dose"]:
            dose_quantity = Quantity(value=Decimal(75), unit="mcg", system="http://unitsofmeasure.org", code="ug")

        dose_rate = DosageDoseAndRate(doseQuantity=dose_quantity) if dose_quantity else None
        dosage = Dosage(
            text=f"{med['dose']} {freq}",
            timing=timing,
            asNeededBoolean=as_needed,
            route=route_cc(med["route"]),
            doseAndRate=[dose_rate] if dose_rate else None,
        )
        return dosage

    for med in meds:
        mr = MedicationRequest(
            id=str(uuid4()),
            meta=meta_common(),
            status="active",
            intent="order",
            subject=patient_ref,
            encounter=encounter_ref,
            authoredOn=dt_iso(datetime.now(timezone.utc) - timedelta(days=5)),
            medicationCodeableConcept=CodeableConcept(
                coding=[Coding(system="http://www.nlm.nih.gov/research/umls/rxnorm", code=med["rx"], display=med["display"])],
                text=med["display"],
            ),
            dosageInstruction=[dosage_for(med)],
        )
        resources.append(mr.model_dump(exclude_none=True, mode="json"))

    # AllergyIntolerance
    allergy = AllergyIntolerance(
        id=str(uuid4()),
        meta=meta_common(),
        patient=patient_ref,
        clinicalStatus=CodeableConcept(
            coding=[
                Coding(
                    system="http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                    code="active",
                    display="Active",
                )
            ]
        ),
        category=["medication"],
        criticality="high",
        code=CodeableConcept(
            coding=[Coding(system="http://snomed.info/sct", code="91936005", display="Sulfonamide")],
            text="Sulfonamide",
        ),
        onsetString="unknown",
    )
    resources.append(allergy.model_dump(exclude_none=True, mode="json"))

    return resources