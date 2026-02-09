"""FHIR R4 resource imports from fhir.resources library."""

from __future__ import annotations

# Import all FHIR resources we use
from fhir.resources.address import Address
from fhir.resources.allergyintolerance import AllergyIntolerance
from fhir.resources.annotation import Annotation
from fhir.resources.attachment import Attachment
from fhir.resources.binary import Binary
from fhir.resources.careplan import CarePlan
from fhir.resources.codeableconcept import CodeableConcept
from fhir.resources.coding import Coding
from fhir.resources.condition import Condition
from fhir.resources.contactpoint import ContactPoint
from fhir.resources.documentreference import DocumentReference
from fhir.resources.encounter import Encounter
from fhir.resources.humanname import HumanName
from fhir.resources.identifier import Identifier
from fhir.resources.location import Location
from fhir.resources.medication import Medication
from fhir.resources.medicationdispense import MedicationDispense
from fhir.resources.medicationrequest import MedicationRequest
from fhir.resources.observation import Observation
from fhir.resources.organization import Organization
from fhir.resources.patient import Patient
from fhir.resources.period import Period
from fhir.resources.person import Person
from fhir.resources.practitioner import Practitioner
from fhir.resources.practitionerrole import PractitionerRole
from fhir.resources.procedure import Procedure
from fhir.resources.quantity import Quantity
from fhir.resources.reference import Reference
from fhir.resources.resource import Resource as FHIRResource

__all__ = [
    "Address",
    "AllergyIntolerance",
    "Annotation",
    "Attachment",
    "Binary",
    "CarePlan",
    "CodeableConcept",
    "Coding",
    "Condition",
    "ContactPoint",
    "DocumentReference",
    "Encounter",
    "FHIRResource",
    "HumanName",
    "Identifier",
    "Location",
    "Medication",
    "MedicationDispense",
    "MedicationRequest",
    "Observation",
    "Organization",
    "Patient",
    "Period",
    "Person",
    "Practitioner",
    "PractitionerRole",
    "Procedure",
    "Quantity",
    "Reference",
]
