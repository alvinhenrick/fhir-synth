"""Medication resource generators (Medication, MedicationRequest, MedicationDispense)."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from fhir_synth.resources import (
    CodeableConcept,
    Coding,
    Medication,
    MedicationDispense,
    MedicationRequest,
    Quantity,
    Reference,
)

if TYPE_CHECKING:
    from fhir_synth.generator import GenerationContext

MEDICATION_CODES = [
    ("197361", "Metformin 500mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("308136", "Lisinopril 10mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("617993", "Atorvastatin 20mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("866427", "Amoxicillin 500mg capsule", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("259255", "Ibuprofen 200mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("705129", "Omeprazole 20mg capsule", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("848695", "Levothyroxine 50mcg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("312615", "Amlodipine 5mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("238129", "Gabapentin 300mg capsule", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("727316", "Losartan 50mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("284215", "Metoprolol 50mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("835829", "Furosemide 40mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("313782", "Sertraline 50mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("849727", "Escitalopram 10mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("645672", "Clopidogrel 75mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("746104", "Aspirin 81mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("617220", "Warfarin 5mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("316255", "Prednisone 10mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("731370", "Albuterol 90mcg inhaler", "http://www.nlm.nih.gov/research/umls/rxnorm"),
    ("213269", "Montelukast 10mg tablet", "http://www.nlm.nih.gov/research/umls/rxnorm"),
]


def generate_medications(ctx: GenerationContext) -> None:
    """Generate a pool of Medication resources."""
    for code, display, system in MEDICATION_CODES:
        med_id = ctx.id_gen.sequential("Medication", start=1)

        medication = Medication(
            id=med_id,
            code=CodeableConcept(
                text=display,
                coding=[Coding(system=system, code=code, display=display)],
            ),
            status="active",
        )
        ctx.graph.add(medication)


def generate_medication_requests(ctx: GenerationContext) -> None:
    """Generate MedicationRequest resources."""
    patients = ctx.graph.get_all("Patient")
    practitioners = ctx.graph.get_all("Practitioner")
    medications = ctx.graph.get_all("Medication")

    if not practitioners or not medications:
        return

    for patient in patients:
        # 1-4 medication requests per patient
        num_requests = ctx.rng.randint(1, 4)

        for _ in range(num_requests):
            req_id = ctx.id_gen.sequential("MedicationRequest", start=1)

            # Select a random medication from the pool
            medication = ctx.rng.choice(medications)

            authored_dt = ctx.date_gen.random_datetime()
            practitioner = ctx.rng.choice(practitioners)

            from fhir.resources.codeablereference import CodeableReference
            from fhir.resources.dosage import Dosage, DosageDoseAndRate
            from fhir.resources.timing import Timing, TimingRepeat

            med_request = MedicationRequest(
                id=req_id,
                status="active",
                intent="order",
                medication=CodeableReference(
                    reference=Reference(reference=f"Medication/{medication.id}")
                ),
                subject=Reference(reference=f"Patient/{patient.id}"),
                authoredOn=authored_dt,
                requester=Reference(reference=f"Practitioner/{practitioner.id}"),
                dosageInstruction=[
                    Dosage(
                        text=ctx.rng.choice(
                            [
                                "Take 1 tablet by mouth daily",
                                "Take 1 tablet by mouth twice daily",
                                "Take 1-2 tablets by mouth every 6 hours as needed",
                            ]
                        ),
                        timing=Timing(
                            repeat=TimingRepeat(
                                frequency=ctx.rng.randint(1, 3),
                                period=Decimal(1),
                                periodUnit="d",
                            )
                        ),
                        doseAndRate=[
                            DosageDoseAndRate(
                                doseQuantity=Quantity(
                                    value=Decimal(ctx.rng.choice([1, 2, 5, 10, 20, 50])),
                                    unit=ctx.rng.choice(["tablet", "mg", "mL"]),
                                    system="http://unitsofmeasure.org",
                                    code=ctx.rng.choice(["{tbl}", "mg", "mL"]),
                                )
                            )
                        ],
                    )
                ],
            )
            ctx.graph.add(med_request)
            ctx.graph.track_reference(f"MedicationRequest/{req_id}", f"Patient/{patient.id}")


def generate_medication_dispenses(ctx: GenerationContext) -> None:
    """Generate MedicationDispense resources."""
    requests = ctx.graph.get_all("MedicationRequest")

    for request in requests:
        # 60% of requests result in dispense
        if ctx.rng.random() > 0.6:
            continue

        dispense_id = ctx.id_gen.sequential("MedicationDispense", start=1)

        # Dispense occurs 0-5 days after request
        if hasattr(request, "authoredOn") and request.authoredOn:
            request_dt = datetime.fromisoformat(str(request.authoredOn).replace("Z", ""))
            dispense_dt = request_dt + timedelta(days=ctx.rng.randint(0, 5))
        else:
            dispense_dt = ctx.date_gen.random_datetime()
            request_dt = None

        # Validate timeline rule if enabled
        if ctx.plan.validation.med_dispense_after_request and request_dt:
            # Ensure dispense is after request
            if dispense_dt < request_dt:
                dispense_dt = request_dt + timedelta(hours=1)

        from fhir.resources.quantity import Quantity

        # Get medication from request
        request_medication = request.medication if hasattr(request, "medication") else None

        med_dispense = MedicationDispense(
            id=dispense_id,
            status="completed",
            medication=request_medication,
            subject=request.subject if hasattr(request, "subject") else None,
            authorizingPrescription=[Reference(reference=f"MedicationRequest/{request.id}")],
            whenHandedOver=dispense_dt,
            quantity=Quantity(
                value=Decimal(ctx.rng.choice([30, 60, 90])),
                unit="tablet",
                system="http://unitsofmeasure.org",
                code="tablet",
            ),
            daysSupply=Quantity(
                value=Decimal(ctx.rng.choice([30, 60, 90])),
                unit="days",
                system="http://unitsofmeasure.org",
                code="d",
            ),
        )
        ctx.graph.add(med_dispense)

        if (
            hasattr(request, "subject")
            and request.subject
            and hasattr(request.subject, "reference")
        ):
            patient_id = request.subject.reference
            ctx.graph.track_reference(f"MedicationDispense/{dispense_id}", patient_id)
        ctx.graph.track_reference(
            f"MedicationDispense/{dispense_id}", f"MedicationRequest/{request.id}"
        )
