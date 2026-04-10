"""Create a maximally diverse subset of training examples for DSPy optimization.

Reads all (prompt, data) pairs from runs/training_examples/ and selects
N maximally diverse examples based on:

  - Age group (child / young_adult / adult / elderly)
  - Gender (male / female / other)
  - Race/ethnicity (US Core extension)
  - Complexity (# conditions + # medications → low / medium / high)
  - FHIR resource type coverage (Jaccard diversity)

Uses greedy maximin sampling: starts with the most resource-type-diverse
patient, then iteratively picks the patient furthest from all already-selected
patients until N are chosen.

Usage
-----
    python examples/create_diverse_subset.py          # default n=100
    python examples/create_diverse_subset.py --n 50

Output
------
    runs/training_examples_diverse/
        <name>_prompt.txt
        <name>_data.json
        diversity_report.json
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

TRAINING_DIR = Path("runs/training_examples")
OUTPUT_DIR = Path("runs/training_examples_diverse")
RACE_EXT = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"


# ── Feature extraction ────────────────────────────────────────────────────────


def _age_bucket(birth_date_str: str) -> str:
    try:
        bd = datetime.strptime(birth_date_str[:10], "%Y-%m-%d")
        age = (datetime.now() - bd).days // 365
    except Exception:
        return "unknown"
    if age < 18:
        return "child"
    if age < 36:
        return "young_adult"
    if age < 61:
        return "adult"
    return "elderly"


def _extract_race(patient: dict) -> str:
    for ext in patient.get("extension", []):
        if ext.get("url") == RACE_EXT:
            for sub in ext.get("extension", []):
                if sub.get("url") == "text":
                    return sub.get("valueString", "unknown")
                if sub.get("url") == "ombCategory":
                    return sub.get("valueCoding", {}).get("display", "unknown")
    return "unknown"


def _complexity_bucket(n_cond: int, n_med: int) -> str:
    total = n_cond + n_med
    if total <= 3:
        return "low"
    if total <= 10:
        return "medium"
    return "high"


def extract_features(bundle: dict) -> dict:
    patient: dict = {}
    resource_types: set[str] = set()
    conditions: set[str] = set()
    medications: set[str] = set()

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "")
        resource_types.add(rtype)
        if rtype == "Patient":
            patient = resource
        elif rtype == "Condition":
            t = (resource.get("code") or {}).get("text", "")
            if t:
                conditions.add(t)
        elif rtype == "MedicationRequest":
            t = (resource.get("medicationCodeableConcept") or {}).get("text", "")
            if t:
                medications.add(t)

    if not patient:
        return {}

    return {
        "age_bucket": _age_bucket(patient.get("birthDate", "")),
        "gender": patient.get("gender", "unknown"),
        "race": _extract_race(patient),
        "complexity": _complexity_bucket(len(conditions), len(medications)),
        "resource_types": frozenset(resource_types),
        "n_conditions": len(conditions),
        "n_meds": len(medications),
    }


# ── Distance metric ───────────────────────────────────────────────────────────


def distance(a: dict, b: dict) -> float:
    """Weighted diversity distance. Higher = more different."""
    score = 0.0
    for key, weight in [
        ("age_bucket", 1.5),
        ("gender", 1.0),
        ("race", 1.5),
        ("complexity", 1.0),
    ]:
        if a.get(key) != b.get(key):
            score += weight
    ra: frozenset = a.get("resource_types", frozenset())
    rb: frozenset = b.get("resource_types", frozenset())
    if ra or rb:
        jaccard_sim = len(ra & rb) / len(ra | rb)
        score += 2.0 * (1.0 - jaccard_sim)
    return score


# ── Greedy maximin sampling ───────────────────────────────────────────────────


def greedy_diverse_sample(features: list[dict], n: int) -> list[int]:
    """Return indices of N maximally diverse patients."""
    total = len(features)
    if total <= n:
        return list(range(total))

    # Seed: patient with the most resource type diversity
    first = max(range(total), key=lambda i: len(features[i].get("resource_types", set())))
    selected = [first]
    selected_set = {first}
    min_dists = [distance(features[first], features[i]) for i in range(total)]

    while len(selected) < n:
        next_idx = max(
            (i for i in range(total) if i not in selected_set),
            key=lambda i: min_dists[i],
        )
        selected.append(next_idx)
        selected_set.add(next_idx)
        new_d = [distance(features[next_idx], features[i]) for i in range(total)]
        min_dists = [min(min_dists[i], new_d[i]) for i in range(total)]
        if len(selected) % 10 == 0:
            print(f"  Selected {len(selected)}/{n}…")

    return selected


# ── Diversity report ──────────────────────────────────────────────────────────


def _distribution(items: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in items:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


def build_report(selected_features: list[dict]) -> dict:
    return {
        "total_selected": len(selected_features),
        "age_bucket": _distribution([f["age_bucket"] for f in selected_features]),
        "gender": _distribution([f["gender"] for f in selected_features]),
        "race": _distribution([f["race"] for f in selected_features]),
        "complexity": _distribution([f["complexity"] for f in selected_features]),
        "resource_type_coverage": sorted(
            {rt for f in selected_features for rt in f.get("resource_types", set())}
        ),
        "avg_conditions": round(
            sum(f["n_conditions"] for f in selected_features) / len(selected_features), 1
        ),
        "avg_medications": round(
            sum(f["n_meds"] for f in selected_features) / len(selected_features), 1
        ),
    }


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100, help="Number of diverse examples to select")
    parser.add_argument(
        "--input", type=Path, default=TRAINING_DIR, help="Input training_examples directory"
    )
    parser.add_argument(
        "--output", type=Path, default=OUTPUT_DIR, help="Output directory for diverse subset"
    )
    args = parser.parse_args()

    input_dir: Path = args.input
    output_dir: Path = args.output
    n: int = args.n

    # Discover all pairs
    data_files = sorted(input_dir.glob("*_data.json"))
    print(f"Found {len(data_files)} pairs in {input_dir}")

    # Load features
    print("Extracting features…")
    names: list[str] = []
    features: list[dict] = []
    for data_file in data_files:
        prompt_file = input_dir / data_file.name.replace("_data.json", "_prompt.txt")
        if not prompt_file.exists():
            continue
        bundle = json.loads(data_file.read_text())
        feats = extract_features(bundle)
        if not feats:
            continue
        names.append(data_file.stem.replace("_data", ""))
        features.append(feats)

    print(f"  {len(features)} valid patients loaded")

    # Greedy diversity sampling
    print(f"Running greedy maximin sampling (n={n})…")
    selected_indices = greedy_diverse_sample(features, n)

    # Copy selected pairs to output
    output_dir.mkdir(parents=True, exist_ok=True)
    for idx in selected_indices:
        name = names[idx]
        shutil.copy(input_dir / f"{name}_prompt.txt", output_dir / f"{name}_prompt.txt")
        shutil.copy(input_dir / f"{name}_data.json", output_dir / f"{name}_data.json")

    # Write diversity report
    selected_features = [features[i] for i in selected_indices]
    report = build_report(selected_features)
    report_path = output_dir / "diversity_report.json"
    report_path.write_text(json.dumps(report, indent=2))

    print(f"\nDone — {len(selected_indices)} pairs saved to {output_dir}")
    print(f"Diversity report: {report_path}")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
