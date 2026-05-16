"""Resolve bundled / user-supplied compiled DSPy programs to a usable path.

Two pre-optimized programs ship with the wheel under `fhir_synth/data/`:

- `miprov2`   — MIPROv2-optimized program (best quality, larger)
- `bootstrap` — BootstrapFewShot-optimized program (fast, smaller)

Either is selectable by short name from the CLI (`--compiled-program miprov2`)
or from the MCP server (`FHIR_SYNTH_COMPILED=bootstrap`). Users can also pass
a filesystem path to their own compiled program.
"""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

# Short-name → bundled filename
BUNDLED_PROGRAMS: dict[str, str] = {
    "miprov2": "miprov2.json",
    "bootstrap": "bootstrap_few_shot.json",
    "bootstrap_few_shot": "bootstrap_few_shot.json",
}


def list_bundled_programs() -> list[str]:
    """Return the canonical short names of bundled compiled programs."""
    return ["miprov2", "bootstrap"]


def resolve_compiled_program(spec: str | None) -> Path | None:
    """Resolve a compiled-program identifier to a filesystem path.

    Args:
        spec: One of:

            - `None`, `""` or `"none"` — return `None` (caller uses
              the unoptimized DSPy default)
            - `"miprov2"` — bundled MIPROv2 program
            - `"bootstrap"` / `"bootstrap_few_shot"` — bundled BootstrapFewShot
            - any other string — treated as a filesystem path

    Returns:
        Path to a JSON file, or `None` to signal "use unoptimized default".

    Raises:
        FileNotFoundError: if a path-like `spec` does not exist.
    """
    if not spec or spec.lower() == "none":
        return None

    if spec in BUNDLED_PROGRAMS:
        bundled = files("fhir_synth.data").joinpath(BUNDLED_PROGRAMS[spec])
        with as_file(bundled) as path:
            if path.exists():
                # `as_file` may return a temporary path on zip-imports — copy
                # to a stable location so callers can re-read it later.
                return Path(path)
        raise FileNotFoundError(
            f"Bundled compiled program '{spec}' is missing from the installed wheel"
        )

    p = Path(spec).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(
            f"Compiled program not found: {spec} "
            f"(expected one of {list_bundled_programs()} or a filesystem path)"
        )
    return p
