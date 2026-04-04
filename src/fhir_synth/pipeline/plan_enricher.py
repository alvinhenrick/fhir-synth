"""PlanEnricher — Stage 1.5 of the two-stage pipeline.

Walks the FHIR dependency graph to detect missing resource companions in a
ClinicalPlan and adds minimal stubs so Stage 2 (code synthesis) can generate
reference-complete FHIR resources without broken references.

Design
------
- Reads ``enum_reference_types`` from fhir.resources field metadata via
  ``fhir_spec.reference_allowed_types()`` — no hardcoded type lists.
- Uses ``_US_CORE_REFS`` to scope enrichment to US Core must-support fields
  (avoids over-enriching plans with rarely-needed companions).
- Returns an immutable enriched copy — never mutates the original plan.
- Idempotent: calling ``enrich()`` twice produces the same result.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from fhir_synth.pipeline.models import CareTeamMember, ClinicalPlan

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

# US Core must-support reference fields that require a companion resource.
# Maps FHIR resource type → list of field names that Stage 2 must populate.
# Extend this dict when new US Core must-support refs are identified.
_US_CORE_REFS: dict[str, list[str]] = {
    "MedicationRequest": ["requester"],
}

# Preference order when multiple target types can satisfy a reference.
# We pick the simplest / most commonly generated type first.
_PREFERRED_ORDER: list[str] = [
    "Practitioner",
    "PractitionerRole",
    "Organization",
    "Patient",  # only as last resort — subject is already present
    "RelatedPerson",
    "Device",
]

# Default display names for auto-added care team members
_DEFAULT_NAMES: dict[str, str] = {
    "Practitioner": "Dr. Smith",
    "PractitionerRole": "Dr. Smith (Attending)",
    "Organization": "General Hospital",
}


class PlanEnricher:
    """Detect and fill missing FHIR resource dependencies in a ClinicalPlan.

    Implements the following algorithm for each resource type the plan will
    generate:

    1. Look up US Core must-support reference fields for that resource type.
    2. Query ``fhir_spec.reference_allowed_types()`` for the concrete target
       types each field accepts.
    3. Check whether the plan already covers at least one of those target types
       (Patient is always covered; care_team roles cover Practitioner /
       PractitionerRole / Organization).
    4. If none are covered, add a minimal ``CareTeamMember`` stub for the
       preferred target type.
    """

    def enrich(self, plan: ClinicalPlan) -> ClinicalPlan:
        """Return an enriched copy of *plan* with missing companions added.

        If no companions are missing the original plan object is returned
        unchanged (no allocation).
        """
        needed_roles = self._compute_needed_roles(plan)
        if not needed_roles:
            return plan

        current_roles = {m.role for m in plan.care_team}
        additions = [
            CareTeamMember(
                role=role,
                display_name=_DEFAULT_NAMES.get(role, role),
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
        generated = self._resource_types_from_plan(plan)
        covered = self._covered_types(plan)
        needed: list[str] = []
        seen: set[str] = set()

        # Patient is always in every plan but should NOT satisfy provider-role
        # references (e.g. MedicationRequest.requester).  Remove it from the
        # coverage set so we still add a Practitioner when needed.
        provider_covered = covered - {"Patient"}

        for resource_type in sorted(generated):  # sorted for determinism
            for ref_field in _US_CORE_REFS.get(resource_type, []):
                allowed = self._allowed_types(resource_type, ref_field)
                if allowed & provider_covered:
                    continue  # already satisfied by a non-patient provider
                preferred = self._pick_preferred(allowed - {"Patient"})
                if preferred and preferred not in seen:
                    needed.append(preferred)
                    seen.add(preferred)

        return needed

    @staticmethod
    def _resource_types_from_plan(plan: ClinicalPlan) -> set[str]:
        """Derive the set of FHIR resource types the plan will generate."""
        types: set[str] = {"Patient"}
        for patient in plan.patients:
            if patient.conditions:
                types.add("Condition")
            if patient.medications:
                types.add("MedicationRequest")
            if patient.allergies:
                types.add("AllergyIntolerance")
        return types

    @staticmethod
    def _covered_types(plan: ClinicalPlan) -> set[str]:
        """Resource types that are already satisfied by the plan."""
        covered: set[str] = {"Patient"}
        for member in plan.care_team:
            covered.add(member.role)
        return covered

    @staticmethod
    def _allowed_types(resource_type: str, field_name: str) -> set[str]:
        """Ask fhir_spec for the concrete allowed target types for a reference field."""
        from fhir_synth.fhir_spec import reference_allowed_types

        try:
            return set(reference_allowed_types(resource_type).get(field_name, []))
        except ValueError:
            return set()

    @staticmethod
    def _pick_preferred(candidates: set[str]) -> str | None:
        """Return the most preferred type from *candidates* per ``_PREFERRED_ORDER``."""
        for preferred in _PREFERRED_ORDER:
            if preferred in candidates:
                return preferred
        return next(iter(sorted(candidates)), None)
