"""Skill discovery, parsing, and selection following the agentskills.io spec.

Skills are self-contained folders with a `SKILL.md` file that provides
domain knowledge to the LLM as system-prompt context.  Each `SKILL.md`
has YAML frontmatter (`name`, `description`, `resource_types`, `always`)
and a Markdown body loaded on demand.

Per the agentskills.io spec, ``description`` is the selection signal —
selectors embed or tokenise it to decide when the skill applies.

The :class:`SkillLoader` scans one or more directories for skills,
and :class:`SkillSelector` implementations score them against the user
prompt to inject only the relevant skill bodies into the system prompt.

**Selection strategies:**

* :class:`SemanticSelector` (default) — Semantic similarity using local
  ONNX embeddings via `fastembed` (default model
  ``BAAI/bge-small-en-v1.5``) and :mod:`numpy` cosine.  Embeddings are
  cached to disk for instant reload.  Handles synonyms like
  "blood sugar" ↔ "HbA1c".

* :class:`KeywordSelector` — Zero-dependency token overlap on the skill
  description with fuzzy spell tolerance via :mod:`difflib`.  Useful as
  a manual override when embeddings are undesirable.

Follows the `Agent Skills Spec <https://agentskills.io/specification>`_
with one extension field (``resource_types``) for FHIR-domain structural
matching.
"""

from fhir_synth.skills.loader import Skill, SkillLoader
from fhir_synth.skills.selector import KeywordSelector, SemanticSelector, SkillSelector

__all__ = [
    "KeywordSelector",
    "SemanticSelector",
    "Skill",
    "SkillLoader",
    "SkillSelector",
]
