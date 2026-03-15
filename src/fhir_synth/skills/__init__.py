"""Skill discovery, parsing, and selection following the agentskills.io spec.

Skills are self-contained folders with a ``SKILL.md`` file that provides
domain knowledge to the LLM as system-prompt context.  Each ``SKILL.md``
has YAML frontmatter (``name``, ``description``, ``keywords``,
``resource_types``, ``always``) and a Markdown body loaded on demand.

The :class:`SkillLoader` scans one or more directories for skills,
and :class:`SkillSelector` implementations score them against the user prompt
to inject only the relevant skill bodies into the system prompt.

**Selection strategies:**

* :class:`KeywordSelector` (default) — Zero-dependency fuzzy keyword matching
  with typo tolerance using Python's built-in ``difflib``. Handles common
  typos like "diabtes" → "diabetes", "medicaton" → "medication".

* :class:`FaissSelector` (optional) — Semantic similarity using sentence
  embeddings. Requires ``pip install fhir-synth[semantic]``. Best for
  large custom skill sets or when semantic matching is needed.

Follows the `Agent Skills Spec <https://agentskills.io/specification>`_
with lightweight extensions (``keywords``, ``resource_types``, ``always``)
for FHIR-domain selection.
"""

from fhir_synth.skills.loader import Skill, SkillLoader
from fhir_synth.skills.selector import FaissSelector, KeywordSelector, SkillSelector

__all__ = [
    "FaissSelector",
    "KeywordSelector",
    "Skill",
    "SkillLoader",
    "SkillSelector",
]
