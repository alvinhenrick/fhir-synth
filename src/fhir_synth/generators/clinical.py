"""Clinical resource generators (Encounter, Condition, Observation, Procedure, AllergyIntolerance, CarePlan)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from fhir_synth.resources import (
    AllergyIntolerance,
    CarePlan,
    CodeableConcept,
    Coding,
    Condition,
    Encounter,
    Observation,
    Period,
    Procedure,
    Quantity,
    Reference,
)

if TYPE_CHECKING:
    from fhir_synth.generator import GenerationContext


# Clinical terminology samples
ENCOUNTER_TYPES = [
    ("AMB", "ambulatory", "Ambulatory"),
    ("EMER", "emergency", "Emergency"),
    ("IMP", "inpatient", "Inpatient"),
    ("HH", "home", "Home Health"),
]

CONDITION_CODES = [
    ("73211009", "Diabetes mellitus", "SNOMED-CT"),
    ("38341003", "Hypertension", "SNOMED-CT"),
    ("13645005", "Chronic obstructive pulmonary disease", "SNOMED-CT"),
    ("44054006", "Type 2 diabetes mellitus", "SNOMED-CT"),
    ("195967001", "Asthma", "SNOMED-CT"),
]

OBSERVATION_CODES = [
    ("8867-4", "Heart rate", "http://loinc.org", "beats/min"),
    ("8480-6", "Systolic blood pressure", "http://loinc.org", "mmHg"),
    ("8462-4", "Diastolic blood pressure", "http://loinc.org", "mmHg"),
    ("4548-4", "Hemoglobin A1c", "http://loinc.org", "%"),
    ("2093-3", "Total cholesterol", "http://loinc.org", "mg/dL"),
    ("29463-7", "Body weight", "http://loinc.org", "kg"),
    ("8310-5", "Body temperature", "http://loinc.org", "Cel"),
]

PROCEDURE_CODES = [
    ("73761001", "Colonoscopy", "SNOMED-CT"),
    ("268400002", "Blood glucose monitoring", "SNOMED-CT"),
    ("34068001", "Heart valve replacement", "SNOMED-CT"),
    ("80146002", "Appendectomy", "SNOMED-CT"),
]

ALLERGY_CODES = [
    ("387207008", "Penicillin", "SNOMED-CT"),
    ("293586001", "Latex", "SNOMED-CT"),
    ("227037002", "Peanut", "SNOMED-CT"),
    ("102263004", "Eggs", "SNOMED-CT"),
]


def generate_encounters(ctx: GenerationContext) -> None:
    """Generate Encounter resources for each patient."""
    patients = ctx.graph.get_all("Patient")
    practitioners = ctx.graph.get_all("Practitioner")
    locations = ctx.graph.get_all("Location")

    if not practitioners:
        return
    if not locations:
        return

    for patient in patients:
        # Generate 2-8 encounters per patient over the time horizon
        num_encounters = ctx.rng.randint(2, 8)

        for _ in range(num_encounters):
            encounter_id = ctx.id_gen.sequential("Encounter", start=1)
            enc_type_code, enc_type_system, enc_type_display = ctx.rng.choice(ENCOUNTER_TYPES)

            # Generate encounter period
            start_dt = ctx.date_gen.random_datetime()
            # Most encounters are short (hours), some are days
            if ctx.rng.random() < 0.8:
                duration_hours = ctx.rng.randint(1, 8)
                end_dt = start_dt + timedelta(hours=duration_hours)
            else:
                duration_days = ctx.rng.randint(1, 7)
                end_dt = start_dt + timedelta(days=duration_days)

            practitioner = ctx.rng.choice(practitioners)
            location = ctx.rng.choice(locations)

            from fhir.resources.encounter import EncounterLocation, EncounterParticipant

            # The 'class' field in Encounter is a FHIR keyword - use setattr after creation
            # or pass as **kwargs - here we create with minimal fields then update
            encounter = Encounter(
                id=encounter_id,
                status="finished",
                type=[
                    CodeableConcept(
                        text=enc_type_display,
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                                code=enc_type_code,
                                display=enc_type_display,
                            )
                        ],
                    )
                ],
                subject=Reference(reference=f"Patient/{patient.id}"),
                participant=[
                    EncounterParticipant(
                        type=[
                            CodeableConcept(
                                coding=[
                                    Coding(
                                        system="http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                                        code="PPRF",
                                        display="Primary Performer",
                                    )
                                ]
                            )
                        ],
                        actor=Reference(reference=f"Practitioner/{practitioner.id}"),
                    )
                ],
                actualPeriod=Period(start=start_dt, end=end_dt),
                location=[
                    EncounterLocation(
                        location=Reference(reference=f"Location/{location.id}"),
                        status="active",
                    )
                ],
            )
            # Note: The 'class' field from FHIR R4 spec is not available in this fhir.resources version
            # The 'type' field already captures the encounter classification
            ctx.graph.add(encounter)
            ctx.graph.track_reference(f"Encounter/{encounter_id}", f"Patient/{patient.id}")


def generate_conditions(ctx: GenerationContext) -> None:
    """Generate Condition resources."""
    patients = ctx.graph.get_all("Patient")

    for patient in patients:
        # 1-3 conditions per patient
        num_conditions = ctx.rng.randint(1, 3)

        for _ in range(num_conditions):
            condition_id = ctx.id_gen.sequential("Condition", start=1)
            code, display, system = ctx.rng.choice(CONDITION_CODES)

            onset_date = ctx.date_gen.random_date()

            condition = Condition(
                id=condition_id,
                clinicalStatus=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/condition-clinical",
                            code="active",
                        )
                    ]
                ),
                verificationStatus=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
                            code="confirmed",
                        )
                    ]
                ),
                category=[
                    CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/condition-category",
                                code="encounter-diagnosis",
                                display="Encounter Diagnosis",
                            )
                        ]
                    )
                ],
                code=CodeableConcept(
                    text=display,
                    coding=[Coding(system="http://snomed.info/sct", code=code, display=display)],
                ),
                subject=Reference(reference=f"Patient/{patient.id}"),
                onsetDateTime=onset_date,
            )
            ctx.graph.add(condition)
            ctx.graph.track_reference(f"Condition/{condition_id}", f"Patient/{patient.id}")


def generate_observations(ctx: GenerationContext) -> None:
    """Generate Observation resources."""
    patients = ctx.graph.get_all("Patient")
    encounters = ctx.graph.get_all("Encounter")

    # Map encounters to patients
    encounters_by_patient: dict[str, list[Any]] = {}
    for enc in encounters:
        # Access the subject reference properly from Pydantic model
        if hasattr(enc, "subject") and enc.subject:
            patient_ref = (
                enc.subject.reference if hasattr(enc.subject, "reference") else str(enc.subject)
            )
            if patient_ref and patient_ref.startswith("Patient/"):
                patient_id = patient_ref.split("/")[1]
                if patient_id not in encounters_by_patient:
                    encounters_by_patient[patient_id] = []
                encounters_by_patient[patient_id].append(enc)

    for patient in patients:
        patient_encounters = encounters_by_patient.get(patient.id, [])

        # Generate 5-15 observations per patient
        num_observations = ctx.rng.randint(5, 15)

        for _ in range(num_observations):
            obs_id = ctx.id_gen.sequential("Observation", start=1)
            code, display, system, unit = ctx.rng.choice(OBSERVATION_CODES)

            # Link to encounter if available
            encounter_ref = None
            effective_dt = ctx.date_gen.random_datetime()

            if patient_encounters and ctx.rng.random() < 0.6:
                # 60% of observations are encounter-linked
                encounter = ctx.rng.choice(patient_encounters)
                encounter_ref = Reference(reference=f"Encounter/{encounter.id}")
                # Observation occurs during an encounter
                if hasattr(encounter, "period") and encounter.period:
                    period = encounter.period
                    if hasattr(period, "start") and period.start:
                        enc_start = datetime.fromisoformat(str(period.start).replace("Z", ""))
                        if hasattr(period, "end") and period.end:
                            enc_end = datetime.fromisoformat(str(period.end).replace("Z", ""))
                            effective_dt = ctx.date_gen.datetime_between(enc_start, enc_end)

            # Generate plausible value based on observation type
            if "Heart rate" in display:
                value = ctx.rng.uniform(60, 100)
            elif "Systolic" in display:
                value = ctx.rng.uniform(110, 140)
            elif "Diastolic" in display:
                value = ctx.rng.uniform(70, 90)
            elif "A1c" in display:
                value = ctx.rng.uniform(5.0, 8.0)
            elif "cholesterol" in display:
                value = ctx.rng.uniform(150, 250)
            elif "weight" in display:
                value = ctx.rng.uniform(50, 120)
            elif "temperature" in display:
                value = ctx.rng.uniform(36.5, 37.5)
            else:
                value = ctx.rng.uniform(10, 100)

            observation = Observation(
                id=obs_id,
                status="final",
                category=[
                    CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/observation-category",
                                code="vital-signs",
                                display="Vital Signs",
                            )
                        ]
                    )
                ],
                code=CodeableConcept(
                    text=display,
                    coding=[Coding(system=system, code=code, display=display)],
                ),
                subject=Reference(reference=f"Patient/{patient.id}"),
                effectiveDateTime=effective_dt,
                valueQuantity=Quantity(
                    value=round(value, 1), unit=unit, system="http://unitsofmeasure.org", code=unit
                ),
                encounter=encounter_ref,
            )

            ctx.graph.add(observation)
            ctx.graph.track_reference(f"Observation/{obs_id}", f"Patient/{patient.id}")
            if encounter_ref and hasattr(encounter_ref, "reference") and encounter_ref.reference:
                ctx.graph.track_reference(f"Observation/{obs_id}", encounter_ref.reference)


def generate_procedures(ctx: GenerationContext) -> None:
    """Generate Procedure resources."""
    patients = ctx.graph.get_all("Patient")

    for patient in patients:
        # 0-2 procedures per patient
        num_procedures = ctx.rng.randint(0, 2)

        for _ in range(num_procedures):
            proc_id = ctx.id_gen.sequential("Procedure", start=1)
            code, display, system = ctx.rng.choice(PROCEDURE_CODES)

            performed_dt = ctx.date_gen.random_datetime()

            procedure = Procedure(
                id=proc_id,
                status="completed",
                code=CodeableConcept(
                    text=display,
                    coding=[Coding(system="http://snomed.info/sct", code=code, display=display)],
                ),
                subject=Reference(reference=f"Patient/{patient.id}"),
                occurrenceDateTime=performed_dt,
            )
            ctx.graph.add(procedure)
            ctx.graph.track_reference(f"Procedure/{proc_id}", f"Patient/{patient.id}")


def generate_allergies(ctx: GenerationContext) -> None:
    """Generate AllergyIntolerance resources."""
    patients = ctx.graph.get_all("Patient")

    for patient in patients:
        # 0-2 allergies per patient
        num_allergies = ctx.rng.randint(0, 2)

        for _ in range(num_allergies):
            allergy_id = ctx.id_gen.sequential("AllergyIntolerance", start=1)
            code, display, system = ctx.rng.choice(ALLERGY_CODES)

            onset_date = ctx.date_gen.random_date()

            allergy = AllergyIntolerance(
                id=allergy_id,
                clinicalStatus=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                            code="active",
                        )
                    ]
                ),
                verificationStatus=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                            code="confirmed",
                        )
                    ]
                ),
                type=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://hl7.org/fhir/allergy-intolerance-type",
                            code="allergy",
                            display="Allergy",
                        )
                    ]
                ),
                category=["medication"] if "Penicillin" in display else ["food"],
                criticality=ctx.rng.choice(["low", "high"]),
                code=CodeableConcept(
                    text=display,
                    coding=[Coding(system="http://snomed.info/sct", code=code, display=display)],
                ),
                patient=Reference(reference=f"Patient/{patient.id}"),
                onsetDateTime=onset_date,
            )
            ctx.graph.add(allergy)
            ctx.graph.track_reference(f"AllergyIntolerance/{allergy_id}", f"Patient/{patient.id}")


def generate_care_plans(ctx: GenerationContext) -> None:
    """Generate CarePlan resources."""
    patients = ctx.graph.get_all("Patient")

    for patient in patients:
        # 0-1 care plans per patient
        if ctx.rng.random() < 0.3:
            continue

        plan_id = ctx.id_gen.sequential("CarePlan", start=1)

        # Care plan spans 30-180 days
        start_dt = ctx.date_gen.random_datetime()
        duration_days = ctx.rng.randint(30, 180)
        end_dt = start_dt + timedelta(days=duration_days)

        from fhir.resources.careplan import CarePlanActivity
        from fhir.resources.codeablereference import CodeableReference

        care_plan = CarePlan(
            id=plan_id,
            status="active",
            intent="plan",
            title=ctx.rng.choice(
                [
                    "Diabetes Management Plan",
                    "Hypertension Management",
                    "Post-operative Care",
                    "Wellness Program",
                ]
            ),
            description=ctx.rng.choice(
                [
                    "Comprehensive care plan for chronic condition management",
                    "Preventive care and wellness program",
                    "Post-surgical recovery plan",
                ]
            ),
            subject=Reference(reference=f"Patient/{patient.id}"),
            period=Period(start=start_dt, end=end_dt),
            activity=[
                CarePlanActivity(
                    performedActivity=[
                        CodeableReference(
                            concept=CodeableConcept(
                                text="Regular blood glucose monitoring",
                            )
                        )
                    ]
                ),
                CarePlanActivity(
                    performedActivity=[
                        CodeableReference(
                            concept=CodeableConcept(
                                text="Dietary consultation",
                            )
                        )
                    ]
                ),
            ],
        )
        ctx.graph.add(care_plan)
        ctx.graph.track_reference(f"CarePlan/{plan_id}", f"Patient/{patient.id}")
