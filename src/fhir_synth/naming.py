"""Auto-generate run names (Docker-style: adjective_noun).

Uses the `coolname` library to produce memorable, unique names
for each generation run, so users never need to specify `--out`.
"""

from pathlib import Path

from coolname import generate_slug  # type: ignore[attr-defined]


def generate_run_name(n_words: int = 2) -> str:
    """Return a Docker-style slug like `brave_phoenix`.

    Args:
        n_words: Number of words in the slug (default 2).

    Returns:
        Underscore-joined slug, e.g. `"happy_helix"`.
    """
    slug: str = generate_slug(n_words)
    return slug.replace("-", "_")


def create_run_dir(base: Path | None = None) -> Path:
    """Create a uniquely-named run directory under *base*.

    The directory is created immediately so parallel runs
    cannot collide on the same name.

    Args:
        base: Parent directory (default: `./runs`).

    Returns:
        :class:`pathlib.Path` to the newly created run directory,
        e.g. `runs/brave_phoenix/`.
    """
    if base is None:
        base = Path("runs")
    base.mkdir(parents=True, exist_ok=True)

    name = generate_run_name()

    # Handle the (rare) collision by appending a counter
    run_dir = base / name
    if run_dir.exists():
        counter = 2
        while (base / f"{name}_{counter}").exists():
            counter += 1
        run_dir = base / f"{name}_{counter}"

    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
