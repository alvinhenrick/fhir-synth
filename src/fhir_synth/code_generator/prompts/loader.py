"""Prompt loader — reads Markdown templates from the prompts package.

Uses `importlib.resources` so prompts are included in wheels and
editable installations without any build configuration.
"""

import importlib.resources
import logging
from functools import lru_cache
from string import Template

logger = logging.getLogger(__name__)

# Anchor package for importlib.resources
_PACKAGE = "fhir_synth.code_generator.prompts"


def _read(subpath: str) -> str:
    """Read a single file from the prompts package.

    Args:
        subpath: Relative path within the prompts package,
            e.g. `"system/01_role.md"`

    Returns:
        File contents as a string.
    """
    ref = importlib.resources.files(_PACKAGE).joinpath(subpath)
    return ref.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _load_dir(subdir: str) -> str:
    """Load and concatenate all `.md` files in *subdir*, sorted by name.

    Files are expected to use a numeric prefix (e.g. `01_role.md`,
    `02_sandbox.md`) so that `sorted()` gives the correct order.

    The result is cached, so repeated calls are free.
    """
    root = importlib.resources.files(_PACKAGE).joinpath(subdir)
    parts: list[str] = []
    for item in sorted(root.iterdir(), key=lambda p: p.name):
        if str(item.name).endswith(".md"):
            parts.append(item.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def load_prompt(path: str) -> str:
    """Load a single Markdown template file.

    Args:
        path: Relative path inside the prompts package.

    Returns:
        Raw template text (may contain `$variable` placeholders).
    """
    return _read(path)


def load_section(subdir: str) -> str:
    """Load and join every `.md` file in a subdirectory.

    Args:
        subdir: `"system"`, `"clinical"`, or `"templates"`.

    Returns:
        Concatenated text of all files, separated by blank lines.
    """
    return _load_dir(subdir)


def render(template_text: str, **kwargs: str) -> str:
    """Render a `string.Template` with safe substitution.

    Unknown `$placeholders` are left as-is rather than raising.

    Args:
        template_text: Raw template with `$variable` placeholders.
        **kwargs: Values to substitute.

    Returns:
        Rendered string.
    """
    return Template(template_text).safe_substitute(kwargs)
