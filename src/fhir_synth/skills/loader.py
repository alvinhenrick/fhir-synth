"""Skill discovery and parsing.

Scans directories for ``SKILL.md`` files, parses YAML frontmatter per the
`agentskills.io <https://agentskills.io/specification>`_ spec, and returns
:class:`Skill` dataclass instances.
"""

from __future__ import annotations

import importlib.resources
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# agentskills.io spec constraints
MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024

# Regex for YAML frontmatter between --- delimiters
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)

# Package that ships built-in skills
_BUILTIN_PACKAGE = "fhir_synth.skills.builtin"


@dataclass(frozen=True)
class Skill:
    """A parsed skill with metadata and body content.

    Attributes:
        name: Unique skill identifier (lowercase, hyphens).
        description: What the skill does and when to use it.
        body: Markdown instruction body (loaded on demand).
        keywords: Domain-specific trigger words for matching.
        resource_types: FHIR resource types this skill covers.
        always: Whether this skill is always included.
        path: Filesystem path to the SKILL.md file.
        source: Origin of the skill (``"builtin"`` or ``"user"``).
    """

    name: str
    description: str
    body: str
    keywords: list[str] = field(default_factory=list)
    resource_types: list[str] = field(default_factory=list)
    always: bool = False
    path: str = ""
    source: str = "builtin"


def _parse_skill_md(content: str, skill_path: str, source: str = "builtin") -> Skill | None:
    """Parse a ``SKILL.md`` file into a :class:`Skill`.

    Args:
        content: Raw file content with YAML frontmatter.
        skill_path: Path to the file (for logging).
        source: ``"builtin"`` or ``"user"``.

    Returns:
        A :class:`Skill` instance, or ``None`` if parsing fails.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        logger.warning("Skipping %s: no valid YAML frontmatter", skill_path)
        return None

    frontmatter_str, body = match.group(1), match.group(2).strip()

    try:
        meta = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as exc:
        logger.warning("Invalid YAML in %s: %s", skill_path, exc)
        return None

    if not isinstance(meta, dict):
        logger.warning("Skipping %s: frontmatter is not a mapping", skill_path)
        return None

    name = str(meta.get("name", "")).strip()
    description = str(meta.get("description", "")).strip()

    if not name or not description:
        logger.warning("Skipping %s: missing required 'name' or 'description'", skill_path)
        return None

    if len(name) > MAX_SKILL_NAME_LENGTH:
        logger.warning("Skill name too long in %s (%d chars), truncating", skill_path, len(name))
        name = name[:MAX_SKILL_NAME_LENGTH]

    if len(description) > MAX_SKILL_DESCRIPTION_LENGTH:
        logger.warning("Description too long in %s, truncating", skill_path)
        description = description[:MAX_SKILL_DESCRIPTION_LENGTH]

    # Parse extension fields (keywords, resource_types, always)
    raw_keywords = meta.get("keywords", [])
    keywords = [str(k).lower() for k in raw_keywords] if isinstance(raw_keywords, list) else []

    raw_types = meta.get("resource_types", [])
    resource_types = [str(t) for t in raw_types] if isinstance(raw_types, list) else []

    always = bool(meta.get("always", False))

    return Skill(
        name=name,
        description=description,
        body=body,
        keywords=keywords,
        resource_types=resource_types,
        always=always,
        path=skill_path,
        source=source,
    )


def _discover_from_directory(directory: Path, source: str = "user") -> list[Skill]:
    """Scan a directory for skill folders containing ``SKILL.md``.

    Args:
        directory: Root directory to scan.
        source: Origin label for discovered skills.

    Returns:
        List of parsed skills.
    """
    skills: list[Skill] = []

    if not directory.is_dir():
        return skills

    for child in sorted(directory.iterdir()):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            content = skill_md.read_text(encoding="utf-8")
            skill = _parse_skill_md(content, str(skill_md), source=source)
            if skill is not None:
                skills.append(skill)
        except OSError as exc:
            logger.warning("Could not read %s: %s", skill_md, exc)

    return skills


def _discover_builtin() -> list[Skill]:
    """Discover built-in skills shipped with the package.

    Uses ``importlib.resources`` so skills are found in installed wheels
    and editable installs alike.

    Returns:
        List of built-in skills.
    """
    skills: list[Skill] = []

    try:
        root = importlib.resources.files(_BUILTIN_PACKAGE)
    except (ModuleNotFoundError, FileNotFoundError):
        logger.debug("No built-in skills package found at %s", _BUILTIN_PACKAGE)
        return skills

    for item in sorted(root.iterdir(), key=lambda p: p.name):
        if not hasattr(item, "iterdir"):
            continue  # not a directory
        # Look for SKILL.md inside each subdirectory
        try:
            skill_md = item.joinpath("SKILL.md")
            content = skill_md.read_text(encoding="utf-8")
            skill = _parse_skill_md(content, str(skill_md), source="builtin")
            if skill is not None:
                skills.append(skill)
        except (FileNotFoundError, TypeError, OSError):
            continue  # no SKILL.md in this dir

    return skills


class SkillLoader:
    """Discovers and manages skills from built-in and user directories.

    Skills are loaded in priority order: built-in (lowest) → user dirs
    (highest). When two skills share the same name, the higher-priority
    version wins.

    Args:
        user_dirs: Optional list of user-provided skill directories.
            Later entries take priority over earlier ones.

    Example::

        loader = SkillLoader(user_dirs=[Path("~/.fhir-synth/skills")])
        skills = loader.discover()
    """

    def __init__(self, user_dirs: list[Path] | None = None) -> None:
        self._user_dirs = user_dirs or []
        self._skills: list[Skill] | None = None  # lazy cache

    def discover(self) -> list[Skill]:
        """Scan all sources and return de-duplicated skills.

        Built-in skills are loaded first, then user directories in order.
        Later sources override earlier ones by name.

        Returns:
            List of discovered skills.
        """
        if self._skills is not None:
            return self._skills

        by_name: dict[str, Skill] = {}

        # 1. Built-in skills (lowest priority)
        for skill in _discover_builtin():
            by_name[skill.name] = skill

        # 2. User directories (in order, later = higher priority)
        for user_dir in self._user_dirs:
            expanded = Path(user_dir).expanduser()
            for skill in _discover_from_directory(expanded, source="user"):
                by_name[skill.name] = skill

        self._skills = list(by_name.values())
        logger.info(
            "Discovered %d skills (%d built-in, %d user)",
            len(self._skills),
            sum(1 for s in self._skills if s.source == "builtin"),
            sum(1 for s in self._skills if s.source == "user"),
        )
        return self._skills

    def reset(self) -> None:
        """Clear the cached skill list, forcing re-discovery on next call."""
        self._skills = None
