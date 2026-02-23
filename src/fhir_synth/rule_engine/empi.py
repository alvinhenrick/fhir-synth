"""EMPI (Enterprise Master Patient Index) resource generation utilities."""

from typing import Any


def generate_empi_resources(
    persons: int,
    systems: list[str] | None = None,
    include_organizations: bool = True,
) -> list[dict[str, Any]]:
    """Generate EMPI-style Person and Patient resources.

    Each Person is linked to one Patient per source system (EMR). Optionally
    creates Organization resources for each system and links Patients to them.

    Args:
        persons: Number of Person resources to generate
        systems: Source system identifiers (e.g., ["emr1", "emr2"])
        include_organizations: Whether to create Organization resources

    Returns:
        List of FHIR resources (Organization, Person, Patient)
    """
    if persons < 1:
        raise ValueError("persons must be >= 1")

    systems = systems or ["emr1", "emr2"]
    resources: list[dict[str, Any]] = []

    organizations: dict[str, dict[str, Any]] = {}
    if include_organizations:
        for system in systems:
            org_id = f"org-{system}"
            organizations[system] = {
                "resourceType": "Organization",
                "id": org_id,
                "name": system,
                "identifier": [{"system": "urn:emr", "value": system}],
            }
        resources.extend(organizations.values())

    for i in range(1, persons + 1):
        person_id = f"person-{i}"
        person_links = []
        patient_resources = []

        for system in systems:
            patient_id = f"{system}-patient-{i}"
            patient_resource: dict[str, Any] = {
                "resourceType": "Patient",
                "id": patient_id,
                "identifier": [{"system": f"urn:emr:{system}", "value": patient_id}],
            }
            if include_organizations:
                patient_resource["managingOrganization"] = {
                    "reference": f"Organization/{organizations[system]['id']}"
                }
            patient_resources.append(patient_resource)
            person_links.append({"target": {"reference": f"Patient/{patient_id}"}})

        person_resource = {
            "resourceType": "Person",
            "id": person_id,
            "link": person_links,
        }

        resources.append(person_resource)
        resources.extend(patient_resources)

    return resources

