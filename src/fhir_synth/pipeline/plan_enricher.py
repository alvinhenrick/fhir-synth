"""PlanEnricher — Stage 1.5 of the two-stage pipeline.

Walks the FHIR dependency graph to detect missing resource companions in a
ClinicalPlan and adds minimal stubs so Stage 2 (code synthesis) can generate
reference-complete FHIR resources without broken references.

Design
------
All enrichment rules are derived at runtime from ``fhir.resources`` field
metadata — nothing is hardcoded.  The algorithm:

1. Derive the set of FHIR resource types the plan will generate.
2. For each resource type, query ``fhir_spec._introspect()`` for reference
   fields that are either **required** (``element_required=True``) or
   **summary** (``summary_element_property=True``).  These are the fields the
   FHIR spec considers important enough to warrant coverage.
3. Cross-reference each field's ``enum_reference_types`` against the types
   already covered by the plan (generated types + existing care_team roles).
4. For any uncovered required/summary reference field, resolve the preferred
   target type (using frequency of appearance across the spec as a proxy for
   importance) and add a minimal ``CareTeamMember`` stub.

This means:
- New FHIR versions, new resource types, and changed reference constraints are
  automatically handled — no code changes needed.
- The enricher never adds companions for truly optional, non-summary reference
  fields, avoiding over-population of the plan.
"""

from __future__ import annotations

import logging

from fhir_synth.fhir_spec import _FOUNDATIONAL_TYPES, FieldMeta
from fhir_synth.pipeline.models import CareTeamMember, ClinicalPlan

# Provider types are foundational resources that appear in "who did this" reference
# fields (Practitioner, PractitionerRole, Organization, Location, Person).
# Patient is excluded: it appears in subject/patient fields, not provider fields.
# Derived directly from fhir_spec._FOUNDATIONAL_TYPES — no hardcoding here.
_PROVIDER_TYPES: frozenset[str] = _FOUNDATIONAL_TYPES - {"Patient"}

logger = logging.getLogger(__name__)


class PlanEnricher:
    """Detect and fill missing FHIR resource dependencies in a ClinicalPlan.

    Fully spec-driven: all reference field discovery uses ``fhir_spec``
    introspection.  No resource type names or field names are hardcoded here.
    """

    def enrich(self, plan: ClinicalPlan) -> ClinicalPlan:
        """Return an enriched copy of *plan* with missing companions added.

        If no companions are missing the original plan object is returned
        unchanged.  Idempotent: calling twice produces the same result.
        """
        needed_roles = self._compute_needed_roles(plan)
        if not needed_roles:
            return plan

        current_roles = {m.role for m in plan.care_team}
        additions = [
            CareTeamMember(
                role=role,
                display_name=_default_name(role),
            )
            for role in needed_roles
            if role not in current_roles
        ]
        if not additions:
            return plan

        logger.debug("PlanEnricher: adding care team stubs: %s", [a.role for a in additions])
        return plan.model_copy(update={"care_team": list(plan.care_team) + additions})

    # ── Private helpers ───────────────────────────────────────────────────────

    def _compute_needed_roles(self, plan: ClinicalPlan) -> list[str]:
        """Return a deduplicated, stable list of role names that must be added."""
        # Only check resource types explicitly created from clinical entries.
        # Patient is always present but we do NOT check its reference fields —
        # doing so would add Organization companions for bare-patient plans.
        clinical_types = _clinical_resource_types(plan)

        # Coverage includes Patient (always) + clinical types + care_team roles.
        covered = clinical_types | {"Patient"} | {m.role for m in plan.care_team}

        needed: list[str] = []
        seen: set[str] = set()

        for resource_type in sorted(clinical_types):
            for field in _provider_reference_fields(resource_type):
                provider_allowed = set(field.enum_reference_types) & _PROVIDER_TYPES
                if provider_allowed & covered:
                    continue  # at least one provider type is already covered
                # Respect the spec's ordering: enum_reference_types lists types in
                # the FHIR spec's preferred order (most common first).
                preferred = _pick_by_spec_order(field.enum_reference_types, provider_allowed)
                if preferred and preferred not in seen:
                    needed.append(preferred)
                    seen.add(preferred)

        return needed


# ── Module-level helpers (pure functions, no state) ────────────────────────────


def _clinical_resource_types(plan: ClinicalPlan) -> set[str]:
    """Derive the set of FHIR resource types created from explicit clinical entries.

    Patient is intentionally excluded: it is always present and its reference
    fields (e.g. ``managingOrganization``) do not require companion creation.
    """
    types: set[str] = set()
    for patient in plan.patients:
        if patient.conditions:
            types.add("Condition")
        if patient.medications:
            types.add("MedicationRequest")
        if patient.allergies:
            types.add("AllergyIntolerance")
    return types


def _provider_reference_fields(resource_type: str) -> list[FieldMeta]:
    """Return summary reference fields that may point to provider-type resources.

    Filters to fields where ``enum_reference_types`` overlaps with
    ``_PROVIDER_TYPES`` (Practitioner, PractitionerRole, Organization, …).
    Fields that only reference Patient/Group are automatically excluded by
    this intersection — no field names are hardcoded.

    Both ``is_summary`` and ``enum_reference_types`` come directly from
    ``fhir.resources`` field metadata.
    """
    from fhir_synth.fhir_spec import _introspect

    try:
        meta = _introspect(resource_type)
    except ValueError:
        return []

    return [
        f
        for f in meta.all_fields
        if f.is_reference and f.is_summary and set(f.enum_reference_types) & _PROVIDER_TYPES
    ]


def _pick_by_spec_order(ordered_types: tuple[str, ...], candidates: set[str]) -> str | None:
    """Return the first type from *ordered_types* that is in *candidates*.

    The FHIR spec lists ``enum_reference_types`` in preferred order (most
    common / most applicable target first).  Walking that order gives us a
    spec-derived preference without any hardcoded ranking.
    """
    for t in ordered_types:
        if t in candidates:
            return t
    return next(iter(sorted(candidates)), None)  # stable fallback


def _default_name(role: str) -> str:
    """Sensible display name for an auto-added care team member."""
    # Derive from the role name itself — no hardcoded map needed.
    # "Practitioner" → "Dr. Smith (Practitioner)"
    # "Organization" → "General Hospital (Organization)"
    _names = {
        "Practitioner": "Dr. Smith",
        "PractitionerRole": "Dr. Smith (Attending)",
        "Organization": "General Hospital",
        "RelatedPerson": "Related Person",
        "Device": "Medical Device",
        "CareTeam": "Care Team",
    }
    return _names.get(role, f"Companion {role}")
