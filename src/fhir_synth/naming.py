"""Auto-generate run names (Docker-style: adjective_noun).

Uses the ``coolname`` library to produce memorable, unique names
for each generation run, so users never need to specify ``--out``.
"""

from __future__ import annotations

from pathlib import Path

from coolname import generate_slug  # type: ignore[attr-defined]


def generate_run_name(n_words: int = 2) -> str:
    """Return a Docker-style slug like ``brave_phoenix``.

    Args:
        n_words: Number of words in the slug (default 2).

    Returns:
        Underscore-joined slug, e.g. ``"happy_helix"``.
    """
    slug: str = generate_slug(n_words)
    return slug.replace("-", "_")


def resolve_run_name(base: Path, name: str | None = None) -> str:
    """Return a unique run name under *base*, generating one if needed.

    When a collision occurs (e.g. ``runs/brave_phoenix.ndjson`` already
    exists), a numeric suffix is appended (``brave_phoenix_2``).

    Args:
        base: Parent directory to check for collisions (e.g. ``./runs``).
        name: Explicit name (auto-generated when ``None``).

    Returns:
        The resolved name string (no path, no extension).
    """
    resolved: str = name if name is not None else generate_run_name()

    # Check if any file with this stem already exists
    if _name_exists(base, resolved):
        counter = 2
        while _name_exists(base, f"{resolved}_{counter}"):
            counter += 1
        resolved = f"{resolved}_{counter}"

    return resolved


def _name_exists(base: Path, name: str) -> bool:
    """Check if any artifact with this name already exists."""
    return (
        (base / f"{name}.py").exists()
        or (base / f"{name}.ndjson").exists()
        or (base / name).is_dir()
    )
