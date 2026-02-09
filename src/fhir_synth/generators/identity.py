"""Person and Patient generators with multi-org support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fhir_synth.resources import (
    Address,
    ContactPoint,
    HumanName,
    Identifier,
    Patient,
    Person,
    Reference,
)
from fhir_synth.utils import select_from_distribution, weighted_sample

if TYPE_CHECKING:
    from fhir_synth.generator import GenerationContext


# Sample data pools for realistic generation
GIVEN_NAMES_FEMALE = [
    "Emma",
    "Olivia",
    "Ava",
    "Isabella",
    "Sophia",
    "Mia",
    "Charlotte",
    "Amelia",
    "Harper",
    "Evelyn",
]
GIVEN_NAMES_MALE = [
    "Liam",
    "Noah",
    "Oliver",
    "Elijah",
    "James",
    "William",
    "Benjamin",
    "Lucas",
    "Henry",
    "Alexander",
]
FAMILY_NAMES = [
    "Smith",
    "Johnson",
    "Williams",
    "Brown",
    "Jones",
    "Garcia",
    "Miller",
    "Davis",
    "Rodriguez",
    "Martinez",
    "Hernandez",
    "Lopez",
    "Gonzalez",
    "Wilson",
    "Anderson",
    "Thomas",
    "Taylor",
    "Moore",
    "Jackson",
    "Martin",
]
CITIES = [
    "Houston",
    "Dallas",
    "Austin",
    "San Antonio",
    "San Francisco",
    "Los Angeles",
    "New York",
    "Chicago",
    "Phoenix",
    "Philadelphia",
]
STATES = ["TX", "CA", "NY", "IL", "AZ", "PA", "FL", "OH", "GA", "NC"]


def generate_persons_and_patients(ctx: GenerationContext) -> None:
    """Generate Person entities and associated Patient records across source systems."""
    plan = ctx.plan
    pop_config = plan.population

    # Determine if we're using multi-org mode or legacy mode
    if pop_config.sources:
        _generate_multi_org(ctx)
    elif pop_config.patients_per_person:
        _generate_legacy(ctx)
    else:
        # Default: one patient per person
        _generate_simple(ctx)


def _generate_multi_org(ctx: GenerationContext) -> None:
    """Generate persons and patients with multi-org source system support."""
    pop_config = ctx.plan.population
    person_appearance = pop_config.person_appearance
    systems_dist = person_appearance.get("systems_per_person_distribution", {1: 1.0})

    # Convert string keys to int if needed
    systems_dist_int: dict[int, float] = {}
    for k, v in systems_dist.items():
        systems_dist_int[int(k)] = float(v)

    # Build source lookup
    sources_by_id = {s.id: s for s in pop_config.sources}
    source_ids = [s.id for s in pop_config.sources]
    source_weights = [s.weight for s in pop_config.sources]

    for _person_idx in range(pop_config.persons):
        # Generate person identity
        person_id = ctx.id_gen.sequential("Person", start=1)
        gender = ctx.rng.choice(["male", "female"])
        given_pool = GIVEN_NAMES_MALE if gender == "male" else GIVEN_NAMES_FEMALE
        given_name = ctx.rng.choice(given_pool)
        family_name = ctx.rng.choice(FAMILY_NAMES)
        birth_date = ctx.date_gen.random_date()

        # Determine how many source systems this person appears in
        num_systems = select_from_distribution(ctx.rng, systems_dist_int)

        # Select source systems
        if num_systems >= len(pop_config.sources):
            selected_sources = source_ids
        else:
            selected_sources = weighted_sample(ctx.rng, source_ids, source_weights, num_systems)

        # Generate patient records for each source system
        patient_ids: list[str] = []
        for source_id in selected_sources:
            source = sources_by_id[source_id]
            patient_id = ctx.id_gen.namespaced("Patient", source.patient_id_namespace)
            patient_ids.append(patient_id)

            # Get or create org reference
            org_ref = _get_org_reference_for_source(ctx, source_id)

            # Generate patient resource using fhir.resources
            patient = Patient(
                id=patient_id,
                identifier=[
                    Identifier(
                        system=f"https://fhir.{source.organization.name.lower().replace(' ', '')}.com/patient",
                        value=patient_id,
                        use="official",
                    )
                ],
                name=[HumanName(family=family_name, given=[given_name], use="official")],
                gender=gender,
                birthDate=birth_date,
                address=[
                    Address(
                        line=[
                            f"{ctx.rng.randint(100, 9999)} {ctx.rng.choice(['Main', 'Oak', 'Maple', 'Cedar'])} St"
                        ],
                        city=ctx.rng.choice(CITIES),
                        state=ctx.rng.choice(STATES),
                        postalCode=f"{ctx.rng.randint(10000, 99999)}",
                        country="US",
                        use="home",
                    )
                ],
                telecom=[
                    ContactPoint(
                        system="phone",
                        value=f"+1-{ctx.rng.randint(200, 999)}-{ctx.rng.randint(200, 999)}-{ctx.rng.randint(1000, 9999)}",
                        use="mobile",
                    )
                ],
                managingOrganization=org_ref,
            )
            ctx.graph.add(patient)

        # Generate person resource linking to all patients
        from fhir.resources.person import PersonLink

        person_links = [
            PersonLink(target=Reference(reference=f"Patient/{pid}"), assurance="level2")
            for pid in patient_ids
        ]

        person = Person(
            id=person_id,
            identifier=[
                Identifier(
                    system="https://fhir.legitrace.com/person",
                    value=person_id,
                    use="official",
                )
            ],
            name=[HumanName(family=family_name, given=[given_name], use="official")],
            gender=gender,
            birthDate=birth_date,
            link=person_links,
            active=True,
        )
        ctx.graph.add(person)

        # Track references
        for pid in patient_ids:
            ctx.graph.track_reference(f"Person/{person_id}", f"Patient/{pid}")


def _generate_legacy(ctx: GenerationContext) -> None:
    """Generate persons and patients using legacy patients_per_person config."""
    pop_config = ctx.plan.population
    dist_config = pop_config.patients_per_person

    if dist_config is None:
        return

    for _person_idx in range(pop_config.persons):
        person_id = ctx.id_gen.sequential("Person", start=1)
        gender = ctx.rng.choice(["male", "female"])
        given_pool = GIVEN_NAMES_MALE if gender == "male" else GIVEN_NAMES_FEMALE
        given_name = ctx.rng.choice(given_pool)
        family_name = ctx.rng.choice(FAMILY_NAMES)
        birth_date = ctx.date_gen.random_date()

        # Determine number of patients
        if dist_config.fixed is not None:
            num_patients = dist_config.fixed
        elif dist_config.range is not None:
            num_patients = ctx.rng.randint(dist_config.range[0], dist_config.range[1])
        elif dist_config.distribution is not None:
            num_patients = select_from_distribution(ctx.rng, dist_config.distribution)
        else:
            num_patients = 1

        # Generate patients
        patient_ids: list[str] = []
        for _ in range(num_patients):
            patient_id = ctx.id_gen.sequential("Patient", start=1)
            patient_ids.append(patient_id)

            patient = Patient(
                id=patient_id,
                identifier=[
                    Identifier(
                        system="https://fhir.example.com/patient",
                        value=patient_id,
                        use="official",
                    )
                ],
                name=[HumanName(family=family_name, given=[given_name], use="official")],
                gender=gender,
                birthDate=birth_date,
                address=[
                    Address(
                        line=[f"{ctx.rng.randint(100, 9999)} Main St"],
                        city=ctx.rng.choice(CITIES),
                        state=ctx.rng.choice(STATES),
                        postalCode=f"{ctx.rng.randint(10000, 99999)}",
                        use="home",
                    )
                ],
            )
            ctx.graph.add(patient)

        # Generate person
        from fhir.resources.person import PersonLink

        person_links = [
            PersonLink(target=Reference(reference=f"Patient/{pid}"), assurance="level2")
            for pid in patient_ids
        ]

        person = Person(
            id=person_id,
            name=[HumanName(family=family_name, given=[given_name])],
            gender=gender,
            birthDate=birth_date,
            link=person_links,
            active=True,
        )
        ctx.graph.add(person)


def _generate_simple(ctx: GenerationContext) -> None:
    """Simple generation: one patient per person."""
    pop_config = ctx.plan.population

    for _person_idx in range(pop_config.persons):
        person_id = ctx.id_gen.sequential("Person", start=1)
        patient_id = ctx.id_gen.sequential("Patient", start=1)

        gender = ctx.rng.choice(["male", "female"])
        given_pool = GIVEN_NAMES_MALE if gender == "male" else GIVEN_NAMES_FEMALE
        given_name = ctx.rng.choice(given_pool)
        family_name = ctx.rng.choice(FAMILY_NAMES)
        birth_date = ctx.date_gen.random_date()

        patient = Patient(
            id=patient_id,
            identifier=[
                Identifier(
                    system="https://fhir.example.com/patient",
                    value=patient_id,
                    use="official",
                )
            ],
            name=[HumanName(family=family_name, given=[given_name], use="official")],
            gender=gender,
            birthDate=birth_date,
        )
        ctx.graph.add(patient)

        from fhir.resources.person import PersonLink

        person = Person(
            id=person_id,
            name=[HumanName(family=family_name, given=[given_name])],
            gender=gender,
            birthDate=birth_date,
            link=[
                PersonLink(target=Reference(reference=f"Patient/{patient_id}"), assurance="level2")
            ],
            active=True,
        )
        ctx.graph.add(person)


def _get_org_reference_for_source(ctx: GenerationContext, source_id: str) -> Reference:
    """Get or create Organization reference for a source system."""
    # Check if org already exists
    orgs = ctx.graph.get_all("Organization")
    for org_resource in orgs:
        # Check identifiers - access via dict since it's been added to graph
        org_dict = org_resource.dict() if hasattr(org_resource, "dict") else org_resource
        identifiers = org_dict.get("identifier", [])
        for ident in identifiers:
            ident_val = ident.get("value") if isinstance(ident, dict) else ident.value
            if ident_val == source_id:
                org_id = org_dict.get("id") if isinstance(org_dict, dict) else org_resource.id
                return Reference(reference=f"Organization/{org_id}")

    # Not found - should have been created by infrastructure generator
    # Return a placeholder reference
    return Reference(reference=f"Organization/{source_id}")
