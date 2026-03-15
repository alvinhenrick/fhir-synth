"""Auto-discover the full FHIR specification from fhir.resources.

This module introspects the ``fhir.resources`` package to build a complete
catalogue of resource types, data types, and their fields. Supports multiple
FHIR versions (R4B, STU3) through dynamic imports.
Classification uses the class hierarchy (``Resource`` / ``DomainResource`` vs
``Element``) — **nothing is hardcoded**.

Public API
----------
- ``set_fhir_version()`` – set the FHIR version (call before other functions)
- ``resource_names()`` – sorted list of all resource type names
- ``get_resource_class`` – import and return the Pydantic class for a name
- ``required_fields`` – required field names for a resource type
- ``reference_targets`` – which resource types a reference field can point to
- ``spec_summary`` – compact text summary suitable for LLM prompts
- ``class_to_module`` – look up the correct module for any Pydantic class
- ``import_guide`` – compact import reference for LLM prompts
"""

import importlib
import os
from dataclasses import dataclass, field
from functools import cache

from pydantic import BaseModel

# Global state for FHIR version
_FHIR_VERSION = "R4B"  # Default version

# ── Truly internal modules that are not usable FHIR types ─────────────────
_INTERNAL_MODULES: frozenset[str] = frozenset(
    {"fhirtypes", "fhirprimitiveextension", "fhirresourcemodel"}
)


def set_fhir_version(version: str) -> None:
    """Set the FHIR version to use (R4B, STU3, etc.).

    Must be called before any other functions in this module if you want
    to use a non-default version. This clears all cached data and re-discovers
    resources for the new version.

    Args:
        version: FHIR version string (case-insensitive). Supported: R4B, STU3
    """
    global \
        _FHIR_VERSION, \
        _MODULE_MAP, \
        _DATA_TYPE_MAP, \
        _CLASS_MODULE_MAP, \
        _MODULE_CLASSES, \
        CLINICAL_RESOURCES

    # Normalize version to uppercase
    version_upper = version.upper()

    # Map common variations to canonical names
    version_map = {
        "R4B": "R4B",
        "STU3": "STU3",
        "R4": "R4B",  # Allow R4 as an alias for R4B
    }

    canonical_version = version_map.get(version_upper)
    if canonical_version is None:
        supported = ", ".join(sorted(set(version_map.values())))
        raise ValueError(
            f"Unsupported FHIR version: {version!r}. Supported: {supported} (case-insensitive)"
        )

    _FHIR_VERSION = canonical_version
    # Clear all caches when version changes
    get_resource_class.cache_clear()
    _introspect.cache_clear()
    _get_base_classes.cache_clear()
    # Re-discover all resources for the new version
    _MODULE_MAP, _DATA_TYPE_MAP, _CLASS_MODULE_MAP, _MODULE_CLASSES = _discover_all()
    CLINICAL_RESOURCES = _discover_clinical_resources()


def get_fhir_version() -> str:
    """Return the current FHIR version."""
    return _FHIR_VERSION


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


@cache
def _get_base_classes() -> tuple[type, type]:
    """Import and return the base Resource and DomainResource classes for the current version."""
    resource_mod = importlib.import_module(f"fhir.resources.{_FHIR_VERSION}.resource")
    domain_mod = importlib.import_module(f"fhir.resources.{_FHIR_VERSION}.domainresource")
    return resource_mod.Resource, domain_mod.DomainResource


def _discover_all() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, list[str]]]:
    """Scan the current FHIR version package and classify every module.

    Uses the class hierarchy to separate FHIR *resources*
    (``issubclass(cls, Resource)``) from *data types* (everything else).

    Returns:
        Tuple of:
        - resource_map: ``{ClassName: module_name}`` for resource types
        - data_type_map: ``{ClassName: module_name}`` for data types
        - class_module_map: ``{ClassName: module_name}`` for ALL classes
        - module_classes: ``{module_name: [ClassName, ...]}`` reverse lookup
    """
    version_mod = importlib.import_module(f"fhir.resources.{_FHIR_VERSION}")
    base_path = version_mod.__path__[0]
    Resource, DomainResource = _get_base_classes()

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
            mod = importlib.import_module(f"fhir.resources.{_FHIR_VERSION}.{modname}")
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
    mod = importlib.import_module(f"fhir.resources.{_FHIR_VERSION}.{modname}")
    cls = getattr(mod, name, None)
    if cls is None:
        # Try case-insensitive lookup
        for attr in dir(mod):
            if attr.lower() == name.lower() and hasattr(getattr(mod, attr), "model_fields"):
                cls = getattr(mod, attr)
                break
    if cls is None:
        raise ValueError(
            f"Could not find class {name!r} in fhir.resources.{_FHIR_VERSION}.{modname}"
        )
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


def _short_type(annotation: str) -> str:
    """Extract a clean short type name from a Pydantic annotation string."""
    # "typing.Annotated[datetime.datetime, DateTime()]" → "DateTime"
    # "abc.ReferenceType" → "Reference"
    # "<class 'abc.CodeableConceptType'>" → "CodeableConcept"
    # "typing.Annotated[str, Code()]" → "Code"
    for pattern, label in [
        ("DateTime()", "DateTime"),
        ("Instant()", "Instant"),
        ("Date()", "Date"),
        ("Code()", "Code"),
        ("Id()", "Id"),
        ("Uri()", "Uri"),
        ("Markdown()", "Markdown"),
        ("ReferenceType", "Reference"),
        ("CodeableConceptType", "CodeableConcept"),
        ("CodingType", "Coding"),
        ("PeriodType", "Period"),
        ("QuantityType", "Quantity"),
        ("IdentifierType", "Identifier"),
        ("HumanNameType", "HumanName"),
        ("AddressType", "Address"),
        ("ContactPointType", "ContactPoint"),
        ("AttachmentType", "Attachment"),
        ("NarrativeType", "Narrative"),
        ("MetaType", "Meta"),
        ("DurationType", "Duration"),
        ("bool", "boolean"),
    ]:
        if pattern in annotation:
            return label
    return "str" if "str" in annotation else "object"


def spec_summary(resource_types: list[str] | None = None) -> str:
    """Compact text summary of the FHIR spec for the given resources.

    Designed to be injected into LLM system prompts so the model knows
    exactly which fields are required / optional / references, along with
    their types (DateTime, Period, CodeableConcept, etc.).
    """
    types = resource_types or CLINICAL_RESOURCES
    lines: list[str] = [
        f"FHIR {_FHIR_VERSION} Spec — {len(types)} resource types\n",
        "DATA TYPE FORMAT RULES (from the FHIR spec):",
        "  DateTime: date-only OR full datetime with timezone.",
        '    ✓ "2025-03-08"  ✓ "2025-03"  ✓ "2025"  ✓ "2025-03-08T10:30:00+00:00"',
        '    ✗ "2025-03-08T10:30:00"  (has time but no timezone — INVALID)',
        "  Instant: MUST be full datetime with timezone. No date-only.",
        '    ✓ "2025-03-08T10:30:00+00:00"  ✓ "2025-03-08T10:30:00Z"',
        '    ✗ "2025-03-08"  ✗ "2025-03-08T10:30:00"',
        "  In code: always construct with timezone when time is needed:",
        "    datetime(2025, 3, 8, 10, 30, tzinfo=timezone.utc).isoformat()",
        "    For date-only DateTime fields: date(2025, 3, 8).isoformat()",
        "  Decimal: use Decimal (from decimal import Decimal), not float.",
        "",
    ]

    # Skip these internal/noise fields to keep the spec compact
    _skip = frozenset(
        {
            "fhir_comments",
            "implicitRules",
            "language",
            "contained",
            "extension",
            "modifierExtension",
            "text",
        }
    )

    for rt in types:
        try:
            meta = _introspect(rt)
        except ValueError:
            continue

        lines.append(f"{rt}:")

        # Required fields with types
        req_parts = []
        for f in meta.all_fields:
            if f.required:
                req_parts.append(f"    {f.name}: {_short_type(f.type_annotation)}  [REQUIRED]")
        if req_parts:
            lines.extend(req_parts)

        # Key optional fields with types (skip noise fields, cap at 12)
        opt_parts = []
        for f in meta.all_fields:
            if not f.required and f.name not in _skip:
                t = _short_type(f.type_annotation)
                tag = " [ref]" if f.is_reference else ""
                opt_parts.append(f"    {f.name}: {t}{tag}")
        if opt_parts:
            for line in opt_parts[:12]:
                lines.append(line)
            if len(opt_parts) > 12:
                lines.append(f"    … and {len(opt_parts) - 12} more fields")
        lines.append("")

    return "\n".join(lines)


# ── Import guide (all data-type modules derived from introspection) ───────


def import_guide(resource_types: list[str] | None = None) -> str:
    """Compact import guide showing exact ``from fhir.resources.{VERSION}.{mod} import {Cls}`` lines.

    Designed to be injected into LLM prompts so the model uses correct import
    paths and never guesses wrong module names.

    Args:
        resource_types: Resource types being generated (e.g. ``["Patient", "Condition"]``).
            Their modules are always included.  If *None*, ``CLINICAL_RESOURCES`` is used.

    Returns:
        Multi-line string suitable for embedding in a prompt.
    """
    types = resource_types or CLINICAL_RESOURCES

    lines: list[str] = ["VALID IMPORT PATHS (use these exactly):\n", "# Resource types"]

    # 1. Resource modules
    for rt in types:
        modname = _MODULE_MAP.get(rt)
        if modname:
            lines.append(f"from fhir.resources.{_FHIR_VERSION}.{modname} import {rt}")

    # 2. All discovered data-type modules
    lines.append("\n# Data types (complex types used in resource fields)")
    for modname in sorted(_DATA_TYPE_MAP.values()):
        classes = _MODULE_CLASSES.get(modname)
        if classes:
            cls_str = ", ".join(sorted(classes))
            lines.append(f"from fhir.resources.{_FHIR_VERSION}.{modname} import {cls_str}")

    lines.append("\n# Use ONLY the module paths listed above. Do NOT invent module names.")

    return "\n".join(lines)
