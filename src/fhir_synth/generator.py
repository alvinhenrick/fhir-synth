"""Core generation engine with graph-based entity management."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fhir_synth.plan import DatasetPlan
from fhir_synth.utils import DateGenerator, DeterministicRNG, IDGenerator


class EntityGraph:
    """Graph of generated entities with reference tracking."""

    def __init__(self) -> None:
        """Initialize empty graph."""
        self.resources: dict[str, Any] = {}  # Changed to Any to support fhir.resources models
        self.by_type: dict[str, list[str]] = defaultdict(list)
        self.references: dict[str, set[str]] = defaultdict(set)

    def add(self, resource: Any) -> None:
        """Add resource to graph (supports both Pydantic models and dicts)."""
        # Extract resource_type and id from Pydantic model or dict
        if hasattr(resource, "get_resource_type"):
            # Pydantic model from fhir.resources (has get_resource_type() method)
            resource_type = resource.get_resource_type()
            resource_id = resource.id
        elif hasattr(resource, "get"):
            # Dict-like object
            resource_type = resource.get("resourceType")
            resource_id = resource.get("id")
        elif hasattr(resource, "resource_type"):
            # Custom class with resource_type attribute
            resource_type = resource.resource_type
            resource_id = resource.id
        else:
            # Try direct attribute access
            resource_type = getattr(resource, "resourceType", None)
            resource_id = getattr(resource, "id", None)

        if not resource_type or not resource_id:
            raise ValueError(f"Resource must have resourceType and id: {type(resource)}")

        key = f"{resource_type}/{resource_id}"
        self.resources[key] = resource
        self.by_type[resource_type].append(resource_id)

    def get(self, resource_type: str, id: str) -> Any:
        """Get resource by type and ID."""
        key = f"{resource_type}/{id}"
        return self.resources.get(key)

    def get_all(self, resource_type: str) -> list[Any]:
        """Get all resources of a type."""
        ids = self.by_type.get(resource_type, [])
        return [self.resources[f"{resource_type}/{id}"] for id in ids]

    def track_reference(self, from_key: str, to_key: str) -> None:
        """Track a reference from one resource to another."""
        self.references[from_key].add(to_key)

    def get_references_from(self, resource_type: str, id: str) -> set[str]:
        """Get all references from a resource."""
        key = f"{resource_type}/{id}"
        return self.references.get(key, set())


class GenerationContext:
    """Context for deterministic generation."""

    def __init__(self, plan: DatasetPlan) -> None:
        """Initialize generation context."""
        self.plan = plan
        self.graph = EntityGraph()
        self.rng = DeterministicRNG(plan.seed)
        self.id_gen = IDGenerator(self.rng)

        # Parse time bounds
        self.end_date = self._parse_end_date()
        self.start_date = self._parse_start_date()
        self.date_gen = DateGenerator(self.rng, self.start_date, self.end_date)

    def _parse_end_date(self) -> datetime:
        """Parse or default end date."""
        if self.plan.time.end_date:
            dt = datetime.fromisoformat(self.plan.time.end_date)
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        return datetime.now(UTC)

    def _parse_start_date(self) -> datetime:
        """Parse or compute start date."""
        if self.plan.time.start_date:
            dt = datetime.fromisoformat(self.plan.time.start_date)
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        horizon_days = self.plan.time.horizon.to_days()
        return self.end_date - timedelta(days=horizon_days)


class DatasetGenerator:
    """Main dataset generator orchestrating all phases."""

    def __init__(self, plan: DatasetPlan) -> None:
        """Initialize generator with plan."""
        self.plan = plan
        self.ctx = GenerationContext(plan)

    def generate(self) -> EntityGraph:
        """Generate complete dataset."""
        from fhir_synth.generators import (
            clinical,
            documents,
            identity,
            infrastructure,
            medications,
        )

        # Phase 1: Infrastructure (orgs, practitioners, locations)
        infrastructure.generate_organizations(self.ctx)
        infrastructure.generate_practitioners(self.ctx)
        infrastructure.generate_practitioner_roles(self.ctx)
        infrastructure.generate_locations(self.ctx)

        # Phase 2: Identity (persons and patients)
        identity.generate_persons_and_patients(self.ctx)

        # Phase 3: Clinical timeline
        clinical.generate_encounters(self.ctx)
        clinical.generate_conditions(self.ctx)
        clinical.generate_observations(self.ctx)
        clinical.generate_procedures(self.ctx)
        clinical.generate_allergies(self.ctx)

        # Phase 4: Medications
        medications.generate_medications(self.ctx)
        medications.generate_medication_requests(self.ctx)
        medications.generate_medication_dispenses(self.ctx)

        # Phase 5: Care planning
        clinical.generate_care_plans(self.ctx)

        # Phase 6: Documents
        documents.generate_document_references(self.ctx)
        documents.generate_binaries(self.ctx)

        return self.ctx.graph
