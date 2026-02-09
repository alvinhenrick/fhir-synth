"""Output writers for NDJSON, Bundle, and individual files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fhir_synth.generator import EntityGraph
    from fhir_synth.plan import DatasetPlan


def write_output(graph: EntityGraph, plan: DatasetPlan) -> None:
    """Write output based on plan configuration."""
    output_format = plan.outputs.format
    output_path = Path(plan.outputs.path)

    if output_format == "ndjson":
        write_ndjson(graph, plan, output_path)
    elif output_format == "bundle":
        write_bundle(graph, plan, output_path)
    elif output_format == "files":
        write_files(graph, output_path)
    else:
        raise ValueError(f"Unknown output format: {output_format}")


def write_ndjson(graph: EntityGraph, plan: DatasetPlan, output_path: Path) -> None:
    """Write resources as NDJSON."""
    output_path.mkdir(parents=True, exist_ok=True)

    split_by_type = plan.outputs.ndjson.get("split_by_resource_type", False)

    if split_by_type:
        # Write separate file per resource type
        for resource_type in sorted(graph.by_type.keys()):
            resources = graph.get_all(resource_type)
            file_path = output_path / f"{resource_type}.ndjson"

            with open(file_path, "w") as f:
                for resource in resources:
                    # Convert fhir.resources Pydantic model to dict
                    if hasattr(resource, "model_dump"):
                        resource_dict = resource.model_dump(mode="json", exclude_none=True)
                    elif hasattr(resource, "dict"):
                        resource_dict = resource.dict()
                    else:
                        resource_dict = dict(resource)
                    json.dump(resource_dict, f, separators=(",", ":"))
                    f.write("\n")
    else:
        # Single NDJSON file with all resources
        file_path = output_path / "output.ndjson"

        with open(file_path, "w") as f:
            # Write in deterministic order: by resource type, then by ID
            for resource_type in sorted(graph.by_type.keys()):
                resources = graph.get_all(resource_type)
                # Sort by ID for deterministic output
                resources_sorted = sorted(resources, key=lambda r: r.id)
                for resource in resources_sorted:
                    # Convert fhir.resources Pydantic model to dict
                    if hasattr(resource, "model_dump"):
                        resource_dict = resource.model_dump(mode="json", exclude_none=True)
                    elif hasattr(resource, "dict"):
                        resource_dict = resource.dict()
                    else:
                        resource_dict = dict(resource)
                    json.dump(resource_dict, f, separators=(",", ":"))
                    f.write("\n")


def write_bundle(graph: EntityGraph, plan: DatasetPlan, output_path: Path) -> None:
    """Write resources as FHIR Bundle."""
    output_path.mkdir(parents=True, exist_ok=True)

    bundle_type = plan.outputs.bundle_type or "collection"

    # Collect all resources in deterministic order
    entries = []
    for resource_type in sorted(graph.by_type.keys()):
        resources = graph.get_all(resource_type)
        resources_sorted = sorted(resources, key=lambda r: r.id)

        for resource in resources_sorted:
            # Convert fhir.resources Pydantic model to dict
            if hasattr(resource, "model_dump"):
                resource_dict = resource.model_dump(mode="json", exclude_none=True)
            elif hasattr(resource, "dict"):
                resource_dict = resource.dict()
            else:
                resource_dict = dict(resource)
            entry: dict[str, Any] = {"resource": resource_dict}

            if bundle_type == "transaction":
                # Add transaction metadata
                resource_type_val = getattr(resource, "resource_type", resource.get("resourceType"))
                resource_id_val = getattr(resource, "id", resource.get("id"))
                entry["request"] = {
                    "method": "PUT",
                    "url": f"{resource_type_val}/{resource_id_val}",
                }

            entries.append(entry)

    bundle = {
        "resourceType": "Bundle",
        "type": bundle_type,
        "entry": entries,
    }

    file_path = output_path / "bundle.json"
    with open(file_path, "w") as f:
        json.dump(bundle, f, indent=2)


def write_files(graph: EntityGraph, output_path: Path) -> None:
    """Write individual JSON files per resource."""
    output_path.mkdir(parents=True, exist_ok=True)

    for resource_type in graph.by_type.keys():
        # Create a subdirectory per resource type
        type_dir = output_path / resource_type
        type_dir.mkdir(exist_ok=True)

        resources = graph.get_all(resource_type)
        for resource in resources:
            # Convert fhir.resources Pydantic model to dict
            if hasattr(resource, "model_dump"):
                resource_dict = resource.model_dump(mode="json", exclude_none=True)
            elif hasattr(resource, "dict"):
                resource_dict = resource.dict()
            else:
                resource_dict = dict(resource)
            file_path = type_dir / f"{resource.id}.json"
            with open(file_path, "w") as f:
                json.dump(resource_dict, f, indent=2)
