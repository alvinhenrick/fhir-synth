"""Infrastructure resource generators (Organization, Practitioner, Location)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fhir_synth.generators.identity import (
    CITIES,
    FAMILY_NAMES,
    GIVEN_NAMES_FEMALE,
    GIVEN_NAMES_MALE,
    STATES,
)
from fhir_synth.resources import (
    Address,
    ContactPoint,
    HumanName,
    Identifier,
    Location,
    Organization,
    Practitioner,
    PractitionerRole,
)

if TYPE_CHECKING:
    from fhir_synth.generator import GenerationContext


ORGANIZATION_TYPES = [
    "Healthcare Provider",
    "Hospital Department",
    "Organizational team",
    "Government",
    "Payer",
]


def generate_organizations(ctx: GenerationContext) -> None:
    """Generate Organization resources."""
    pop_config = ctx.plan.population

    # Generate orgs from source systems if defined
    if pop_config.sources:
        for source in pop_config.sources:
            org_id = ctx.id_gen.sequential("Organization", start=1)

            from fhir.resources.codeableconcept import CodeableConcept
            from fhir.resources.coding import Coding
            from fhir.resources.extendedcontactdetail import ExtendedContactDetail

            org = Organization(
                id=org_id,
                identifier=[
                    Identifier(
                        system=ident.system,
                        value=ident.value,
                        use="official",
                    )
                    for ident in source.organization.identifiers
                ]
                or [
                    Identifier(
                        system="urn:org",
                        value=source.id,
                        use="official",
                    )
                ],
                active=True,
                name=source.organization.name,
                type=[
                    CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/organization-type",
                                code="prov",
                                display="Healthcare Provider",
                            )
                        ],
                        text="Healthcare Provider",
                    )
                ],
                contact=[
                    ExtendedContactDetail(
                        telecom=[
                            ContactPoint(
                                system="phone",
                                value=f"+1-{ctx.rng.randint(200, 999)}-{ctx.rng.randint(200, 999)}-{ctx.rng.randint(1000, 9999)}",
                                use="work",
                            )
                        ],
                        address=Address(
                            line=[f"{ctx.rng.randint(100, 9999)} Medical Plaza"],
                            city=ctx.rng.choice(CITIES),
                            state=ctx.rng.choice(STATES),
                            postalCode=f"{ctx.rng.randint(10000, 99999)}",
                            country="US",
                        ),
                    )
                ],
            )
            ctx.graph.add(org)
    else:
        # Generate the default pool of organizations (3-5)
        num_orgs = ctx.rng.randint(3, 5)
        for _ in range(num_orgs):
            org_id = ctx.id_gen.sequential("Organization", start=1)
            org_name = f"{ctx.rng.choice(['General', 'Regional', 'Community', 'University'])} {ctx.rng.choice(['Hospital', 'Medical Center', 'Health System', 'Clinic'])}"

            from fhir.resources.codeableconcept import CodeableConcept
            from fhir.resources.coding import Coding
            from fhir.resources.extendedcontactdetail import ExtendedContactDetail

            org = Organization(
                id=org_id,
                identifier=[
                    Identifier(
                        system="https://fhir.example.com/org",
                        value=org_id,
                        use="official",
                    )
                ],
                active=True,
                name=org_name,
                type=[
                    CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/organization-type",
                                code="prov",
                                display="Healthcare Provider",
                            )
                        ]
                    )
                ],
                contact=[
                    ExtendedContactDetail(
                        telecom=[
                            ContactPoint(
                                system="phone",
                                value=f"+1-{ctx.rng.randint(200, 999)}-{ctx.rng.randint(200, 999)}-{ctx.rng.randint(1000, 9999)}",
                                use="work",
                            )
                        ],
                        address=Address(
                            line=[f"{ctx.rng.randint(100, 9999)} Medical Plaza"],
                            city=ctx.rng.choice(CITIES),
                            state=ctx.rng.choice(STATES),
                            postalCode=f"{ctx.rng.randint(10000, 99999)}",
                            country="US",
                        ),
                    )
                ],
            )
            ctx.graph.add(org)


def generate_practitioners(ctx: GenerationContext) -> None:
    """Generate Practitioner resources."""
    # Generate pool of practitioners (10-20)
    num_practitioners = ctx.rng.randint(10, 20)

    for _ in range(num_practitioners):
        prac_id = ctx.id_gen.sequential("Practitioner", start=1)
        gender = ctx.rng.choice(["male", "female"])
        given_pool = GIVEN_NAMES_MALE if gender == "male" else GIVEN_NAMES_FEMALE
        given_name = ctx.rng.choice(given_pool)
        family_name = ctx.rng.choice(FAMILY_NAMES)

        from fhir.resources.codeableconcept import CodeableConcept
        from fhir.resources.coding import Coding
        from fhir.resources.practitioner import PractitionerQualification

        practitioner = Practitioner(
            id=prac_id,
            identifier=[
                Identifier(
                    system="https://fhir.example.com/practitioner",
                    value=prac_id,
                    use="official",
                ),
                Identifier(
                    system="http://hl7.org/fhir/sid/us-npi",
                    value=f"{ctx.rng.randint(1000000000, 9999999999)}",
                    use="official",
                ),
            ],
            active=True,
            name=[
                HumanName(
                    family=family_name,
                    given=[given_name],
                    prefix=[ctx.rng.choice(["Dr.", "Dr.", "Dr.", "NP", "PA"])],
                    use="official",
                )
            ],
            gender=gender,
            telecom=[
                ContactPoint(
                    system="email",
                    value=f"{given_name.lower()}.{family_name.lower()}@example.com",
                    use="work",
                )
            ],
            qualification=[
                PractitionerQualification(
                    code=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/v2-0360",
                                code="MD",
                                display="Doctor of Medicine",
                            )
                        ],
                        text="Doctor of Medicine",
                    )
                )
            ],
        )
        ctx.graph.add(practitioner)


def generate_practitioner_roles(ctx: GenerationContext) -> None:
    """Generate PractitionerRole resources linking Practitioners to Organizations."""
    practitioners = ctx.graph.get_all("Practitioner")
    organizations = ctx.graph.get_all("Organization")
    locations = ctx.graph.get_all("Location")

    if not organizations:
        return

    from fhir.resources.codeableconcept import CodeableConcept
    from fhir.resources.coding import Coding
    from fhir.resources.reference import Reference

    # Common practitioner roles/specialties
    roles = [
        ("doctor", "Doctor", "http://terminology.hl7.org/CodeSystem/practitioner-role"),
        ("nurse", "Nurse", "http://terminology.hl7.org/CodeSystem/practitioner-role"),
    ]

    specialties = [
        ("394802001", "General Medicine", "http://snomed.info/sct"),
        ("394579002", "Cardiology", "http://snomed.info/sct"),
        ("394582007", "Dermatology", "http://snomed.info/sct"),
        ("394589003", "Nephrology", "http://snomed.info/sct"),
        ("394591006", "Neurology", "http://snomed.info/sct"),
    ]

    for practitioner in practitioners:
        # Each practitioner has 1-2 roles
        num_roles = ctx.rng.randint(1, 2)

        for _ in range(num_roles):
            role_id = ctx.id_gen.sequential("PractitionerRole", start=1)
            organization = ctx.rng.choice(organizations)
            role_code, role_display, role_system = ctx.rng.choice(roles)
            specialty_code, specialty_display, specialty_system = ctx.rng.choice(specialties)

            # Optionally link to a location
            location_refs = None
            if locations and ctx.rng.random() > 0.3:
                location = ctx.rng.choice(locations)
                location_refs = [Reference(reference=f"Location/{location.id}")]

            practitioner_role = PractitionerRole(
                id=role_id,
                active=True,
                practitioner=Reference(reference=f"Practitioner/{practitioner.id}"),
                organization=Reference(reference=f"Organization/{organization.id}"),
                code=[
                    CodeableConcept(
                        coding=[
                            Coding(
                                system=role_system,
                                code=role_code,
                                display=role_display,
                            )
                        ],
                        text=role_display,
                    )
                ],
                specialty=[
                    CodeableConcept(
                        coding=[
                            Coding(
                                system=specialty_system,
                                code=specialty_code,
                                display=specialty_display,
                            )
                        ],
                        text=specialty_display,
                    )
                ],
                location=location_refs,
            )
            ctx.graph.add(practitioner_role)
            ctx.graph.track_reference(
                f"PractitionerRole/{role_id}", f"Practitioner/{practitioner.id}"
            )
            ctx.graph.track_reference(
                f"PractitionerRole/{role_id}", f"Organization/{organization.id}"
            )


def generate_locations(ctx: GenerationContext) -> None:
    """Generate Location resources."""
    # Generate pool of locations (5-10)
    num_locations = ctx.rng.randint(5, 10)

    location_types = [
        ("Clinic", "OUTPHARM"),
        ("Hospital", "HOSP"),
        ("Emergency Room", "ER"),
        ("Operating Room", "OR"),
        ("Intensive Care Unit", "ICU"),
    ]

    for _ in range(num_locations):
        loc_id = ctx.id_gen.sequential("Location", start=1)
        loc_type_name, loc_type_code = ctx.rng.choice(location_types)

        from fhir.resources.codeableconcept import CodeableConcept
        from fhir.resources.coding import Coding
        from fhir.resources.extendedcontactdetail import ExtendedContactDetail

        location = Location(
            id=loc_id,
            identifier=[
                Identifier(
                    system="https://fhir.example.com/location",
                    value=loc_id,
                    use="official",
                )
            ],
            status="active",
            name=f"{loc_type_name} {ctx.rng.randint(1, 99)}",
            mode="instance",
            type=[
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/v3-RoleCode",
                            code=loc_type_code,
                            display=loc_type_name,
                        )
                    ],
                    text=loc_type_name,
                )
            ],
            address=Address(
                line=[f"{ctx.rng.randint(100, 9999)} Medical Center Dr"],
                city=ctx.rng.choice(CITIES),
                state=ctx.rng.choice(STATES),
                postalCode=f"{ctx.rng.randint(10000, 99999)}",
                country="US",
            ),
            contact=[
                ExtendedContactDetail(
                    telecom=[
                        ContactPoint(
                            system="phone",
                            value=f"+1-{ctx.rng.randint(200, 999)}-{ctx.rng.randint(200, 999)}-{ctx.rng.randint(1000, 9999)}",
                            use="work",
                        )
                    ]
                )
            ],
        )
        ctx.graph.add(location)
