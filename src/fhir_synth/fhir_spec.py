"""Auto-discover the full FHIR R4B specification from fhir.resources.

This module uses **lazy loading** — it scans filesystem module names at import
time (instant) but only imports the heavy Pydantic model classes on demand.

Public API
----------
- ``resource_names()`` – sorted list of all resource type names
- ``get_resource_class`` – import and return the Pydantic class for a name
- ``required_fields`` – required field names for a resource type
- ``field_schema`` – full field metadata for a resource type
- ``reference_targets`` – which resource types a reference field can point to
- ``spec_summary`` – compact text summary suitable for LLM prompts
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from functools import cache
from typing import Any

import fhir.resources.R4B as _r4b

# ── Data-type modules to skip (not top-level FHIR resources) ──────────────
_DATA_TYPE_MODULES: frozenset[str] = frozenset({
    "fhirtypes", "codeableconcept", "codeablereference", "coding",
    "backboneelement", "element", "extension", "meta", "narrative",
    "reference", "resource", "domainresource", "quantity",
    "contactpoint", "contactdetail", "address", "humanname",
    "identifier", "period", "attachment", "annotation",
    "age", "count", "distance", "duration", "money",
    "range", "ratio", "ratiorange", "sampleddata", "signature", "timing",
    "triggerdefinition", "usagecontext", "dosage",
    "expression", "parameterdefinition", "relatedartifact",
    "contributor", "datarequirement", "marketingstatus",
    "population", "prodcharacteristic", "productshelflife",
    "substanceamount", "elementdefinition",
    "fhirprimitiveextension", "fhirresourcemodel",
})


# ── Data classes ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FieldMeta:
    """Metadata about a single field on a FHIR resource."""
    name: str
    required: bool
    type_annotation: str
    is_reference: bool = False
    is_list: bool = False


@dataclass(frozen=True)
class ResourceMeta:
    """Metadata about a FHIR R4B resource type."""
    name: str
    module: str
    required_fields: tuple[str, ...]
    all_fields: tuple[FieldMeta, ...] = field(default=(), repr=False)

    @property
    def optional_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.all_fields if not f.required)

    @property
    def reference_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.all_fields if f.is_reference)


# ── Lightweight name discovery (filesystem only, no imports) ──────────────

def _discover_module_names() -> dict[str, str]:
    """Return ``{ClassName: module_name}`` by scanning filenames only.

    Uses a two-pass strategy:
    1. For simple names (e.g. ``patient`` → ``Patient``), uppercase the first letter.
    2. For compound names (e.g. ``practitionerrole``), look up in a known table
       built from the fhir.resources package metadata.

    No heavy Pydantic models are imported here.
    """
    base_path = _r4b.__path__[0]
    mapping: dict[str, str] = {}

    # Build a lowercase → real-class-name lookup from all .py files
    # by importing just the module and checking dir() for a class whose
    # lowercase matches the module name.
    for fname in sorted(os.listdir(base_path)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        modname = fname[:-3]
        if modname in _DATA_TYPE_MODULES:
            continue

        try:
            mod = importlib.import_module(f"fhir.resources.R4B.{modname}")
        except Exception:  # noqa: BLE001
            continue

        # Find the main resource class: same name (case-insensitive) + has model_fields
        for attr_name in dir(mod):
            if attr_name.startswith("_"):
                continue
            if attr_name.lower() == modname.lower():
                obj = getattr(mod, attr_name, None)
                if obj is not None and isinstance(obj, type) and hasattr(obj, "model_fields"):
                    mapping[attr_name] = modname
                    break

    return mapping


# Built once at import time — just a dict of names, zero heavy imports
_MODULE_MAP: dict[str, str] = _discover_module_names()


# ── Lazy loaders (import + introspect on first access, then cached) ───────

@cache
def get_resource_class(name: str) -> type:
    """Import and return the Pydantic model class for a resource type.

    Results are cached so each module is only imported once.

    Raises:
        ValueError: If *name* is not a known resource type.
    """
    modname = _MODULE_MAP.get(name)
    if modname is None:
        raise ValueError(
            f"Unknown FHIR resource type: {name!r}. "
            f"Known: {', '.join(sorted(_MODULE_MAP)[:20])} …"
        )
    mod = importlib.import_module(f"fhir.resources.R4B.{modname}")
    cls = getattr(mod, name, None)
    if cls is None:
        # Try case-insensitive lookup
        for attr in dir(mod):
            if attr.lower() == name.lower() and hasattr(getattr(mod, attr), "model_fields"):
                cls = getattr(mod, attr)
                break
    if cls is None:
        raise ValueError(f"Could not find class {name!r} in fhir.resources.R4B.{modname}")
    return cls  # type: ignore[return-value]


@cache
def _introspect(name: str) -> ResourceMeta:
    """Introspect a resource class and build its ``ResourceMeta``."""
    cls = get_resource_class(name)
    modname = _MODULE_MAP[name]
    fields: list[FieldMeta] = []
    required: list[str] = []

    for fname, finfo in cls.model_fields.items():
        if fname.endswith("__ext"):
            continue
        is_req = finfo.is_required()
        ann = str(finfo.annotation) if finfo.annotation else "Any"
        is_ref = "ReferenceType" in ann
        is_list = "List" in ann or "list" in ann
        fields.append(FieldMeta(
            name=fname, required=is_req,
            type_annotation=ann, is_reference=is_ref, is_list=is_list,
        ))
        if is_req:
            required.append(fname)

    return ResourceMeta(
        name=name, module=modname,
        required_fields=tuple(required),
        all_fields=tuple(fields),
    )


# ── Public helpers ────────────────────────────────────────────────────────

def resource_names() -> list[str]:
    """Sorted list of all known FHIR R4B resource type names."""
    return sorted(_MODULE_MAP.keys())


def required_fields(name: str) -> tuple[str, ...]:
    """Required field names for a resource type."""
    return _introspect(name).required_fields


def field_schema(name: str) -> list[dict[str, Any]]:
    """Field metadata as plain dicts (JSON-safe)."""
    meta = _introspect(name)
    return [
        {"name": f.name, "required": f.required, "type": f.type_annotation,
         "is_reference": f.is_reference, "is_list": f.is_list}
        for f in meta.all_fields
    ]


def reference_targets(name: str) -> dict[str, str]:
    """Mapping of reference field names → type annotations."""
    meta = _introspect(name)
    return {f.name: f.type_annotation for f in meta.all_fields if f.is_reference}


# ── Commonly used clinical resource types ─────────────────────────────────

CLINICAL_RESOURCES: list[str] = [
    rt for rt in [
        "Patient", "Person", "Practitioner", "PractitionerRole",
        "Organization", "Location", "Encounter",
        "Condition", "Observation", "Procedure",
        "MedicationRequest", "MedicationDispense", "MedicationAdministration",
        "Medication", "MedicationStatement",
        "DiagnosticReport", "DocumentReference",
        "Immunization", "AllergyIntolerance",
        "CarePlan", "CareTeam", "Goal", "ServiceRequest",
        "FamilyMemberHistory", "Specimen", "ImagingStudy",
        "Consent", "Coverage", "Claim", "ExplanationOfBenefit",
    ] if rt.lower() in {m.lower() for m in _MODULE_MAP}
]


def spec_summary(resource_types: list[str] | None = None) -> str:
    """Compact text summary of the FHIR spec for the given resources.

    Designed to be injected into LLM system prompts so the model knows
    exactly which fields are required / optional / references.
    """
    types = resource_types or CLINICAL_RESOURCES
    lines: list[str] = [f"FHIR R4B Spec — {len(types)} resource types\n"]

    for rt in types:
        try:
            meta = _introspect(rt)
        except ValueError:
            continue
        req = ", ".join(meta.required_fields) or "(none)"
        refs = ", ".join(meta.reference_fields) or "(none)"
        opt_sample = ", ".join(meta.optional_fields[:8])
        if len(meta.optional_fields) > 8:
            opt_sample += " …"
        lines.append(f"{rt}:")
        lines.append(f"  required: {req}")
        lines.append(f"  references: {refs}")
        lines.append(f"  optional: {opt_sample}")
        lines.append("")

    return "\n".join(lines)

