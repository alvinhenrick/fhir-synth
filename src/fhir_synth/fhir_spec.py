"""Auto-discover the full FHIR specification from fhir.resources.

This module introspects the `fhir.resources` package to build a complete
catalogue of resource types, data types, and their fields. Supports multiple
FHIR versions (R4B, STU3) through dynamic imports.
Classification uses the class hierarchy (`Resource` / `DomainResource` vs
`Element`) — **nothing is hardcoded**.

Public API
----------
- `set_fhir_version()` – set the FHIR version (call before other functions)
- `resource_names()` – sorted list of all resource type names
- `get_resource_class` – import and return the Pydantic class for a name
- `required_fields` – required field names for a resource type
- `reference_targets` – which resource types a reference field can point to
- `spec_summary` – compact text summary suitable for LLM prompts
- `class_to_module` – look up the correct module for any Pydantic class
- `import_guide` – compact import reference for LLM prompts
"""

import importlib
import os
from dataclasses import dataclass, field
from functools import cache

from pydantic import BaseModel


# Lazy import to avoid circular dependency — us_core_validation does not import fhir_spec
def _us_core_must_support() -> dict[str, frozenset[str]]:
    from fhir_synth.code_generator.us_core_validation import must_support_by_resource

    return must_support_by_resource()


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
    choice_group: str | None = None
    choice_required: bool = False
    is_summary: bool = False
    enum_reference_types: tuple[str, ...] = ()
    alias: str | None = (
        None  # JSON alias when it differs from the Python name (e.g. "class" for class_)
    )


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

    @property
    def choice_groups(self) -> dict[str, tuple["FieldMeta", ...]]:
        """Group fields by their choice-type base name (e.g. `medication`)."""
        groups: dict[str, list[FieldMeta]] = {}
        for f in self.all_fields:
            if f.choice_group is not None:
                groups.setdefault(f.choice_group, []).append(f)
        return {k: tuple(v) for k, v in groups.items()}

    @property
    def choice_required_groups(self) -> dict[str, tuple["FieldMeta", ...]]:
        """Choice groups where at least one variant is required."""
        return {k: v for k, v in self.choice_groups.items() if any(f.choice_required for f in v)}


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
    (`issubclass(cls, Resource)`) from *data types* (everything else).

    Returns:
        Tuple of:
        - resource_map: `{ClassName: module_name}` for resource types
        - data_type_map: `{ClassName: module_name}` for data types
        - class_module_map: `{ClassName: module_name}` for ALL classes
        - module_classes: `{module_name: [ClassName, ...]}` reverse lookup
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
    """Introspect a resource class and build its `ResourceMeta`."""
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
        choice_group = extras.get("one_of_many")
        choice_required = bool(extras.get("one_of_many_required"))
        is_summary = bool(extras.get("summary_element_property"))
        raw_enum_ref = extras.get("enum_reference_types")
        enum_ref: tuple[str, ...] = (
            tuple(str(v) for v in raw_enum_ref) if isinstance(raw_enum_ref, list) else ()
        )
        # Detect JSON alias mismatches (e.g. class_ → "class") so spec_summary can warn the LLM
        raw_alias = finfo.alias
        json_alias = str(raw_alias) if raw_alias and str(raw_alias) != fname else None
        fields.append(
            FieldMeta(
                name=fname,
                required=is_req,
                type_annotation=ann,
                is_reference=is_ref,
                is_list=is_list,
                choice_group=choice_group if isinstance(choice_group, str) else None,
                choice_required=choice_required,
                is_summary=is_summary,
                enum_reference_types=enum_ref,
                alias=json_alias,
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


@cache
def _introspect_backbone(class_name: str) -> tuple[FieldMeta, ...] | None:
    """Introspect any Pydantic class by name (backbone elements, data types, etc.).

    Unlike `_introspect`, works for any class in `_CLASS_MODULE_MAP`, not just
    top-level resources.  Returns None if the class cannot be found or imported.
    Used by `spec_summary` to expand backbone element fields inline.
    """
    modname = _CLASS_MODULE_MAP.get(class_name)
    if modname is None:
        return None
    try:
        mod = importlib.import_module(f"fhir.resources.{_FHIR_VERSION}.{modname}")
        cls = getattr(mod, class_name, None)
        if cls is None or not hasattr(cls, "model_fields"):
            return None
    except Exception:
        return None

    fields: list[FieldMeta] = []
    for fname, finfo in cls.model_fields.items():
        if fname.endswith("__ext"):
            continue
        ann = str(finfo.annotation) if finfo.annotation else "Any"
        extras = finfo.json_schema_extra if isinstance(finfo.json_schema_extra, dict) else {}
        is_req = finfo.is_required() or bool(extras.get("element_required"))
        raw_alias = finfo.alias
        json_alias = str(raw_alias) if raw_alias and str(raw_alias) != fname else None
        choice_group = extras.get("one_of_many")
        fields.append(
            FieldMeta(
                name=fname,
                required=is_req,
                type_annotation=ann,
                is_reference="ReferenceType" in ann,
                is_list="List" in ann or "list" in ann,
                choice_group=choice_group if isinstance(choice_group, str) else None,
                choice_required=bool(extras.get("one_of_many_required")),
                alias=json_alias,
            )
        )
    return tuple(fields) if fields else None


# Types that are well-known to LLMs and don't need inline expansion.
# Backbone elements NOT in this set will have their sub-fields shown in spec_summary.
_WELL_KNOWN_FHIR_TYPES: frozenset[str] = frozenset(
    {
        "Reference",
        "CodeableConcept",
        "Coding",
        "Period",
        "Quantity",
        "Age",
        "Duration",
        "Count",
        "Distance",
        "Money",
        "SimpleQuantity",
        "Identifier",
        "HumanName",
        "Address",
        "ContactPoint",
        "Attachment",
        "Narrative",
        "Meta",
        "Annotation",
        "Range",
        "Ratio",
        "Timing",
        "Dosage",
        "SampledData",
        "Signature",
    }
)

# Primitive-like labels — sub-fields of this type are not worth showing
_PRIMITIVES: frozenset[str] = frozenset(
    {
        "str",
        "boolean",
        "object",
        "DateTime",
        "Instant",
        "Date",
        "Code",
        "Id",
        "Uri",
        "Markdown",
        "int",
        "float",
    }
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


def reference_allowed_types(name: str) -> dict[str, list[str]]:
    """Mapping of reference field names → allowed target resource type names.

    Derived from `FieldMeta.enum_reference_types` — populated at introspection
    time from `enum_reference_types` in `json_schema_extra`.

    Example::

        reference_allowed_types("MedicationRequest")["requester"]
        # → ['Practitioner', 'PractitionerRole', 'Organization', 'Patient', ...]

    Args:
        name: FHIR resource type name, e.g. `"MedicationRequest"`.

    Returns:
        Dict mapping field name → list of allowed resource type names.
        Fields without explicit `enum_reference_types` (open references) are omitted.
    """
    meta = _introspect(name)
    return {f.name: list(f.enum_reference_types) for f in meta.all_fields if f.enum_reference_types}


# ── Clinical resources (derived by introspection) ─────────────────────────

# Foundational resource types always included in the clinical subset
_FOUNDATIONAL_TYPES: frozenset[str] = frozenset(
    {"Patient", "Person", "Practitioner", "PractitionerRole", "Organization", "Location"}
)


def _discover_clinical_resources() -> list[str]:
    """Derive clinical resource types by introspecting reference fields.

    A resource is considered "clinical" if it has a `subject`, `patient`,
    or `encounter` reference field, or if it is a foundational type
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
        ("AgeType", "Age"),
        ("DurationType", "Duration"),
        ("CountType", "Count"),
        ("DistanceType", "Distance"),
        ("MoneyType", "Money"),
        ("SimpleQuantityType", "SimpleQuantity"),
        ("IdentifierType", "Identifier"),
        ("HumanNameType", "HumanName"),
        ("AddressType", "Address"),
        ("ContactPointType", "ContactPoint"),
        ("AttachmentType", "Attachment"),
        ("NarrativeType", "Narrative"),
        ("MetaType", "Meta"),
        ("bool", "boolean"),
    ]:
        if pattern in annotation:
            return label
    # Generic fallback: resolve any XxxType → Xxx via the class module map.
    # This covers all backbone elements and named FHIR types not listed above.
    import re as _re

    for m in _re.finditer(r"\b(\w+?)Type\b", annotation):
        candidate = m.group(1)
        if candidate in _CLASS_MODULE_MAP:
            return candidate
    return "str" if "str" in annotation else "object"


def _backbone_expansion(field_name: str, type_label: str, indent: int = 6) -> list[str]:
    """Return indented sub-field lines for a backbone element type.

    Only expands types that are not well-known (e.g. MedicationRequestDispenseRequest)
    so the LLM sees the exact sub-field types without guessing.  Never recurses.
    """
    if type_label in _WELL_KNOWN_FHIR_TYPES or type_label in _PRIMITIVES:
        return []
    sub_fields = _introspect_backbone(type_label)
    if not sub_fields:
        return []
    pad = " " * indent
    lines: list[str] = []
    shown = 0
    for sf in sub_fields:
        if sf.name in ("fhir_comments", "id", "extension", "modifierExtension"):
            continue
        st = _short_type(sf.type_annotation)
        req_tag = " [REQUIRED]" if sf.required else ""
        alias_note = f' [JSON key: "{sf.alias}"]' if sf.alias else ""
        lines.append(f"{pad}{sf.name}: {st}{req_tag}{alias_note}")
        shown += 1
        if shown >= 8:
            remaining = (
                sum(
                    1
                    for s in sub_fields
                    if s.name not in ("fhir_comments", "id", "extension", "modifierExtension")
                )
                - shown
            )
            if remaining > 0:
                lines.append(f"{pad}… and {remaining} more")
            break
    return lines


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

    us_core = _us_core_must_support()

    for rt in types:
        try:
            meta = _introspect(rt)
        except ValueError:
            continue

        us_core_fields = us_core.get(rt, frozenset())
        lines.append(f"{rt}:")

        # Required fields with types
        req_parts = []
        for f in meta.all_fields:
            if f.required:
                field_json_name = f.alias or f.name
                us_core_tag = "  [US CORE]" if field_json_name in us_core_fields else ""
                alias_note = f'  [JSON key: "{f.alias}"]' if f.alias else ""
                t = _short_type(f.type_annotation)
                req_parts.append(f"    {f.name}: {t}  [REQUIRED]{us_core_tag}{alias_note}")
                req_parts.extend(_backbone_expansion(f.name, t, indent=6))
        if req_parts:
            lines.extend(req_parts)

        # Choice-type [x] field groups — shown prominently, exempt from cap
        choice_field_names: set[str] = set()
        for group_name, group_fields in meta.choice_groups.items():
            choice_field_names.update(f.name for f in group_fields)
            tag = "[ONE REQUIRED]" if group_fields[0].choice_required else "[pick one]"
            variants = ", ".join(
                f"{f.name} ({_short_type(f.type_annotation)})" for f in group_fields
            )
            lines.append(f"    {group_name}[x] {tag}: {variants}")

        # Key optional fields with types (skip noise fields AND choice fields, cap at 12)
        # US Core must-support optional fields are always shown (exempt from cap)
        opt_us_core: list[str] = []
        opt_regular: list[str] = []
        for f in meta.all_fields:
            if not f.required and f.name not in _skip and f.name not in choice_field_names:
                t = _short_type(f.type_annotation)
                ref_tag = " [ref]" if f.is_reference else ""
                alias_note = f' [JSON key: "{f.alias}"]' if f.alias else ""
                field_json_name = f.alias or f.name
                entry_lines = [f"    {f.name}: {t}{ref_tag}{alias_note}"]
                entry_lines.extend(_backbone_expansion(f.name, t, indent=6))
                if field_json_name in us_core_fields:
                    opt_us_core.extend(
                        [f"    {f.name}: {t}{ref_tag}  [US CORE]{alias_note}"]
                        + _backbone_expansion(f.name, t, indent=6)
                    )
                else:
                    opt_regular.extend(entry_lines)

        lines.extend(opt_us_core)  # always show US Core optional fields
        for line in opt_regular[:12]:
            lines.append(line)
        remaining = len(opt_regular) - 12
        if remaining > 0:
            lines.append(f"    … and {remaining} more fields")
        lines.append("")

    return "\n".join(lines)


# ── Import guide (all data-type modules derived from introspection) ───────


def import_guide(resource_types: list[str] | None = None) -> str:
    """Compact import guide showing exact `from fhir.resources.{VERSION}.{mod} import {Cls}` lines.

    Designed to be injected into LLM prompts so the model uses correct import
    paths and never guesses wrong module names.

    Args:
        resource_types: Resource types being generated (e.g. `["Patient", "Condition"]`).
            Their modules are always included.  If *None*, `CLINICAL_RESOURCES` is used.

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
