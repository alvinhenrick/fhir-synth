"""Auto-discover the full FHIR R4B specification from fhir.resources.

This module introspects the ``fhir.resources.R4B`` package at import time to
build a complete catalogue of resource types, data types, and their fields.
Classification uses the class hierarchy (``Resource`` / ``DomainResource`` vs
``Element``) — **nothing is hardcoded**.

Public API
----------
- ``resource_names()`` – sorted list of all resource type names
- ``get_resource_class`` – import and return the Pydantic class for a name
- ``required_fields`` – required field names for a resource type
- ``field_schema`` – full field metadata for a resource type
- ``reference_targets`` – which resource types a reference field can point to
- ``spec_summary`` – compact text summary suitable for LLM prompts
- ``class_to_module`` – look up the correct module for any Pydantic class
- ``import_guide`` – compact import reference for LLM prompts
"""

import importlib
import os
from dataclasses import dataclass, field
from functools import cache
from typing import Any

import fhir.resources.R4B as _r4b
from fhir.resources.R4B.domainresource import DomainResource
from fhir.resources.R4B.resource import Resource
from pydantic import BaseModel

# ── Truly internal modules that are not usable FHIR types ─────────────────
_INTERNAL_MODULES: frozenset[str] = frozenset(
    {"fhirtypes", "fhirprimitiveextension", "fhirresourcemodel"}
)


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


# ── Single unified scan ──────────────────────────────────────────────────


def _discover_all() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, list[str]]]:
    """Scan ``fhir.resources.R4B`` once and classify every module.

    Uses the class hierarchy to separate FHIR *resources*
    (``issubclass(cls, Resource)``) from *data types* (everything else).

    Returns:
        Tuple of:
        - resource_map: ``{ClassName: module_name}`` for resource types
        - data_type_map: ``{ClassName: module_name}`` for data types
        - class_module_map: ``{ClassName: module_name}`` for ALL classes
        - module_classes: ``{module_name: [ClassName, ...]}`` reverse lookup
    """
    base_path = _r4b.__path__[0]
    resource_map: dict[str, str] = {}
    data_type_map: dict[str, str] = {}
    class_module_map: dict[str, str] = {}
    module_classes: dict[str, list[str]] = {}

    for fname in sorted(os.listdir(base_path)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        modname = fname[:-3]
        if modname in _INTERNAL_MODULES:
            continue

        try:
            mod = importlib.import_module(f"fhir.resources.R4B.{modname}")
        except Exception:  # noqa: BLE001
            continue

        # Find the primary class (name matches module, case-insensitive)
        for attr_name in dir(mod):
            if attr_name.startswith("_"):
                continue
            if attr_name.lower() != modname.lower():
                continue
            obj = getattr(mod, attr_name, None)
            if obj is not None and isinstance(obj, type) and hasattr(obj, "model_fields"):
                # Classify: Resource (including DomainResource) vs data type
                is_resource = issubclass(obj, Resource) and obj not in (
                    Resource,
                    DomainResource,
                )
                if is_resource:
                    resource_map[attr_name] = modname
                else:
                    data_type_map[attr_name] = modname
                break

        # Collect ALL exported Pydantic classes (for class→module lookup)
        for attr_name in dir(mod):
            if attr_name.startswith("_"):
                continue
            obj = getattr(mod, attr_name, None)
            if obj is not None and isinstance(obj, type) and hasattr(obj, "model_fields"):
                if attr_name not in class_module_map:
                    class_module_map[attr_name] = modname
                    module_classes.setdefault(modname, []).append(attr_name)

    return resource_map, data_type_map, class_module_map, module_classes


# Built once at import time
_MODULE_MAP, _DATA_TYPE_MAP, _CLASS_MODULE_MAP, _MODULE_CLASSES = _discover_all()


def class_to_module(class_name: str) -> str | None:
    """Return the module name for a Pydantic class, or None if unknown."""
    return _CLASS_MODULE_MAP.get(class_name)


def data_type_modules() -> list[str]:
    """Sorted list of all discovered data-type module names."""
    return sorted(_DATA_TYPE_MAP.values())


# ── Lazy loaders (import + introspect on first access, then cached) ───────


@cache
def get_resource_class(name: str) -> type[BaseModel]:
    """Import and return the Pydantic model class for a resource type.

    Results are cached so each module is only imported once.

    Raises:
        ValueError: If *name* is not a known resource type.
    """
    modname = _MODULE_MAP.get(name)
    if modname is None:
        raise ValueError(
            f"Unknown FHIR resource type: {name!r}. Known: {', '.join(sorted(_MODULE_MAP)[:20])} …"
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
    return cls  # type: ignore[no-any-return]


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
        # Pydantic is_required() only checks if default is PydanticUndefined.
        # fhir.resources mark FHIR-required fields via element_required in
        # json_schema_extra (e.g. Observation.status has default=None but
        # element_required=True and a custom validator rejects None).
        extras = finfo.json_schema_extra if isinstance(finfo.json_schema_extra, dict) else {}
        is_req = finfo.is_required() or bool(extras.get("element_required"))
        ann = str(finfo.annotation) if finfo.annotation else "Any"
        is_ref = "ReferenceType" in ann
        is_list = "List" in ann or "list" in ann
        fields.append(
            FieldMeta(
                name=fname,
                required=is_req,
                type_annotation=ann,
                is_reference=is_ref,
                is_list=is_list,
            )
        )
        if is_req:
            required.append(fname)

    return ResourceMeta(
        name=name,
        module=modname,
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
        {
            "name": f.name,
            "required": f.required,
            "type": f.type_annotation,
            "is_reference": f.is_reference,
            "is_list": f.is_list,
        }
        for f in meta.all_fields
    ]


def reference_targets(name: str) -> dict[str, str]:
    """Mapping of reference field names → type annotations."""
    meta = _introspect(name)
    return {f.name: f.type_annotation for f in meta.all_fields if f.is_reference}


# ── Clinical resources (derived by introspection) ─────────────────────────

# Foundational resource types always included in the clinical subset
_FOUNDATIONAL_TYPES: frozenset[str] = frozenset(
    {"Patient", "Person", "Practitioner", "PractitionerRole", "Organization", "Location"}
)


def _discover_clinical_resources() -> list[str]:
    """Derive clinical resource types by introspecting reference fields.

    A resource is considered "clinical" if it has a ``subject``, ``patient``,
    or ``encounter`` reference field, or if it is a foundational type
    (Patient, Practitioner, Organization, etc.).
    """
    clinical: set[str] = set(_FOUNDATIONAL_TYPES & set(_MODULE_MAP))

    for name in _MODULE_MAP:
        try:
            meta = _introspect(name)
        except ValueError:
            continue
        field_names = {f.name for f in meta.all_fields}
        if field_names & {"subject", "patient", "encounter", "beneficiary"}:
            clinical.add(name)

    return sorted(clinical)


CLINICAL_RESOURCES: list[str] = _discover_clinical_resources()


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


# ── Import guide (all data-type modules derived from introspection) ───────


def import_guide(resource_types: list[str] | None = None) -> str:
    """Compact import guide showing exact ``from fhir.resources.R4B.{mod} import {Cls}`` lines.

    Designed to be injected into LLM prompts so the model uses correct import
    paths and never guesses wrong module names.

    Args:
        resource_types: Resource types being generated (e.g. ``["Patient", "Condition"]``).
            Their modules are always included.  If *None*, ``CLINICAL_RESOURCES`` is used.

    Returns:
        Multi-line string suitable for embedding in a prompt.
    """
    types = resource_types or CLINICAL_RESOURCES

    lines: list[str] = ["VALID IMPORT PATHS (use these exactly):\n"]

    # 1. Resource modules
    lines.append("# Resource types")
    for rt in types:
        modname = _MODULE_MAP.get(rt)
        if modname:
            lines.append(f"from fhir.resources.R4B.{modname} import {rt}")

    # 2. All discovered data-type modules
    lines.append("\n# Data types (complex types used in resource fields)")
    for modname in sorted(_DATA_TYPE_MAP.values()):
        classes = _MODULE_CLASSES.get(modname)
        if classes:
            cls_str = ", ".join(sorted(classes))
            lines.append(f"from fhir.resources.R4B.{modname} import {cls_str}")

    lines.append(
        "\n# WARNING: Classes are in the modules listed above."
        "\n# Do NOT invent module names like 'timingrepeat' or 'contactdetail'."
        "\n# e.g., TimingRepeat is in 'timing', not 'timingrepeat'."
    )

    return "\n".join(lines)
