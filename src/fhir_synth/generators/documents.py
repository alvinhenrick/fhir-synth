"""Document resource generators (DocumentReference, Binary)."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from fhir_synth.resources import (
    Attachment,
    Binary,
    CodeableConcept,
    Coding,
    DocumentReference,
    Reference,
)

if TYPE_CHECKING:
    from fhir_synth.generator import GenerationContext


DOCUMENT_TYPES = [
    ("18842-5", "Discharge summary", "http://loinc.org"),
    ("11488-4", "Consultation note", "http://loinc.org"),
    ("34108-1", "Outpatient Progress note", "http://loinc.org"),
    ("11506-3", "Progress note", "http://loinc.org"),
]


def generate_document_references(ctx: GenerationContext) -> None:
    """Generate DocumentReference resources."""
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

        # 30% of patients have documents
        if ctx.rng.random() > 0.3:
            continue

        # 1-3 documents per patient
        num_docs = ctx.rng.randint(1, 3)

        for _ in range(num_docs):
            doc_id = ctx.id_gen.sequential("DocumentReference", start=1)
            code, display, system = ctx.rng.choice(DOCUMENT_TYPES)

            created_dt = ctx.date_gen.random_datetime()

            # Link to encounter if available
            encounter_refs = None
            if patient_encounters and ctx.rng.random() < 0.7:
                encounter = ctx.rng.choice(patient_encounters)
                encounter_refs = [Reference(reference=f"Encounter/{encounter.id}")]

            # Create placeholder binary reference
            binary_id = f"Binary-{doc_id}"

            from fhir.resources.documentreference import DocumentReferenceContent

            doc_ref = DocumentReference(
                id=doc_id,
                status="current",
                type=CodeableConcept(
                    text=display,
                    coding=[Coding(system=system, code=code, display=display)],
                ),
                subject=Reference(reference=f"Patient/{patient.id}"),
                date=created_dt,
                content=[
                    DocumentReferenceContent(
                        attachment=Attachment(
                            contentType="application/pdf",
                            url=f"Binary/{binary_id}",
                            title=display,
                            creation=created_dt,
                        )
                    )
                ],
                context=encounter_refs if encounter_refs else None,
            )

            ctx.graph.add(doc_ref)
            ctx.graph.track_reference(f"DocumentReference/{doc_id}", f"Patient/{patient.id}")
            ctx.graph.track_reference(f"DocumentReference/{doc_id}", f"Binary/{binary_id}")


def generate_binaries(ctx: GenerationContext) -> None:
    """Generate Binary resources for DocumentReferences."""
    doc_refs = ctx.graph.get_all("DocumentReference")

    for doc_ref in doc_refs:
        if hasattr(doc_ref, "content") and doc_ref.content:
            for content in doc_ref.content:
                if hasattr(content, "attachment") and content.attachment:
                    attachment = content.attachment
                    binary_url = attachment.url if hasattr(attachment, "url") else ""

                    if binary_url and binary_url.startswith("Binary/"):
                        binary_id = binary_url.split("/")[1]

                        # Generate small placeholder PDF content
                        placeholder_text = f"Clinical document {binary_id}\n"

                        if (
                            hasattr(doc_ref, "subject")
                            and doc_ref.subject
                            and hasattr(doc_ref.subject, "reference")
                        ):
                            placeholder_text += f"Patient: {doc_ref.subject.reference}\n"
                        else:
                            placeholder_text += "Patient: Unknown\n"

                        if hasattr(doc_ref, "date"):
                            placeholder_text += f"Date: {doc_ref.date}\n"
                        else:
                            placeholder_text += "Date: Unknown\n"

                        if (
                            hasattr(doc_ref, "type")
                            and doc_ref.type
                            and hasattr(doc_ref.type, "text")
                        ):
                            placeholder_text += f"Type: {doc_ref.type.text}\n"
                        else:
                            placeholder_text += "Type: Unknown\n"

                        placeholder_text += "\n[Document content would appear here]\n"

                        # Base64 encode to bytes (Binary.data expects bytes, not string)
                        encoded = base64.b64encode(placeholder_text.encode())

                        content_type = (
                            attachment.contentType
                            if hasattr(attachment, "contentType")
                            else "application/pdf"
                        )

                        binary = Binary(
                            id=binary_id,
                            contentType=content_type,
                            data=encoded,
                        )
                        ctx.graph.add(binary)
