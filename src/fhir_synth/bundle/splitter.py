"""Split a flat list of FHIR resources into per-patient bundles."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _extract_patient_id(resource: dict[str, Any]) -> str | None:
    """Extract the patient ID a resource belongs to.

    Returns the ``id`` for Patient resources, or the referenced patient ID
    from ``subject`` / ``patient`` / ``beneficiary`` fields for others.
    """
    if resource.get("resourceType") == "Patient":
        return resource.get("id")

    for field in ("subject", "patient", "beneficiary"):
        ref = resource.get(field)
        if isinstance(ref, dict):
            reference = ref.get("reference", "")
            match = re.match(r"Patient/(.+)", reference)
            if match:
                return match.group(1)

    return None


def split_resources_by_patient(
    resources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Split a flat resource list into one Bundle per patient.

    Each bundle contains the Patient resource plus all resources that
    reference that patient.  Resources that cannot be linked to any
    patient (e.g. Organization, Practitioner) are included in **every**
    patient bundle, so each bundle is self-contained.

    Returns:
        List of FHIR Bundle dicts (``type: collection``).
    """
    patient_ids: list[str] = []
    patient_resources: dict[str, list[dict[str, Any]]] = {}
    unlinked: list[dict[str, Any]] = []

    # First pass — collect Patient resources (preserving order)
    for r in resources:
        if r.get("resourceType") == "Patient":
            pid = r.get("id", f"unknown-{len(patient_ids)}")
            if pid not in patient_resources:
                patient_ids.append(pid)
                patient_resources[pid] = []
            patient_resources[pid].append(r)

    # Second pass — assign non-Patient resources to their patient
    for r in resources:
        if r.get("resourceType") == "Patient":
            continue
        pid = _extract_patient_id(r)
        if pid and pid in patient_resources:
            patient_resources[pid].append(r)
        else:
            unlinked.append(r)

    # Build one Bundle per patient
    bundles: list[dict[str, Any]] = []
    for pid in patient_ids:
        entries = patient_resources[pid] + unlinked
        bundles.append(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "total": len(entries),
                "entry": [{"resource": r} for r in entries],
            }
        )

    # Edge case: no patients found — return everything in one bundle
    if not bundles and resources:
        bundles.append(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "total": len(resources),
                "entry": [{"resource": r} for r in resources],
            }
        )

    return bundles


def write_split_bundles(
    bundles: list[dict[str, Any]],
    output_dir: Path,
) -> list[Path]:
    """Write each patient bundle to a separate JSON file.

    Files are named ``patient_001.json``, ``patient_002.json``, etc.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, bundle in enumerate(bundles, 1):
        path = output_dir / f"patient_{i:03d}.json"
        path.write_text(json.dumps(bundle, indent=2, default=str))
        paths.append(path)
    return paths


def write_ndjson(
    bundles: list[dict[str, Any]],
    output_path: Path,
) -> Path:
    """Write bundles as NDJSON — one JSON bundle per line."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        for bundle in bundles:
            f.write(json.dumps(bundle, default=str) + "\n")
    return output_path
