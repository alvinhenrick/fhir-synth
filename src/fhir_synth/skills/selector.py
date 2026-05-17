"""Skill selection strategies.

Provides a :class:`SkillSelector` protocol and two concrete implementations:

* :class:`SemanticSelector` (default) — semantic retrieval using `fastembed`
  for local ONNX embeddings (default model `BAAI/bge-small-en-v1.5`,
  ~130 MB, 384-dim) and `numpy` cosine similarity.  Embeddings are
  pre-computed **once** and cached to disk, so later loads are instant.
* :class:`KeywordSelector` — zero-dependency keyword + resource-type
  matching with fuzzy spell tolerance via :mod:`difflib`.  Useful as a
  manual override when embeddings are undesirable.

Both return the :class:`~fhir_synth.skills.loader.Skill` instances ready
for injection into the LLM system prompt.
"""

import difflib
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from fhir_synth.skills.loader import Skill

logger = logging.getLogger(__name__)

# Default cache location for pre-computed embeddings
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "fhir-synth" / "skills"

# Default fastembed model — best size/quality ratio at the 384-dim tier.
# ~130 MB ONNX, beats all-MiniLM-L6-v2 on MTEB retrieval, no PyTorch dep.
DEFAULT_EMBED_MODEL = "BAAI/bge-small-en-v1.5"


# ── Protocol ────────────────────────────────────────────────────────────


@runtime_checkable
class SkillSelector(Protocol):
    """Strategy interface for selecting relevant skills."""

    def select(self, prompt: str, skills: list[Skill]) -> list[Skill]:
        """Return skills relevant to *prompt*.

        Args:
            prompt: User's natural-language request.
            skills: All discovered skills.

        Returns:
            Subset of *skills* that should be injected into the system prompt.
        """
        ...


# ── Keyword selector (zero deps, manual override) ──────────────────────


# Common English stop-words excluded from matching
_STOP_WORDS = frozenset(
    "a an and are as at be by for from has have i in is it of on or that the "
    "to was were will with do not no so if but we my our you your they them "
    "some any all each every this those these can could would should".split()
)

# Regex to tokenise a string into lowercase alphanumeric words
_TOKEN_RE = re.compile(r"[a-z][a-z0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> set[str]:
    """Lowercase tokenise, removing stop words."""
    return {w.lower() for w in _TOKEN_RE.findall(text)} - _STOP_WORDS


class KeywordSelector:
    """Select skills by token overlap between the prompt and skill description.

    Follows the agentskills.io spec: ``description`` is the primary matching
    signal. The selector tokenises the prompt and each skill's
    ``description`` + ``name`` + ``resource_types``, then scores by overlap.

    Selection logic:

    1. Skills with ``always=True`` are always included.
    2. Each remaining skill is scored:

       - exact ``resource_type`` substring hit → +2
       - description / name token overlap → +1 per shared token
       - fuzzy description-token match (typo-tolerant) → +1

    3. Skills with score >= ``min_score`` are included.
    4. **Safe fallback**: if no skill scores high enough, *all* skills are
       included so behaviour is never worse than before skills existed.

    Args:
        min_score: Minimum score for a skill to be selected (default 1).
        fuzzy_threshold: Similarity threshold for fuzzy matching (0.0-1.0,
            default 0.85). Lower = more tolerant of typos, higher = stricter.
    """

    def __init__(self, min_score: int = 1, fuzzy_threshold: float = 0.85) -> None:
        self.min_score = min_score
        self.fuzzy_threshold = fuzzy_threshold

    def _fuzzy_match(self, term: str, prompt_tokens: set[str]) -> bool:
        """Check if *term* fuzzy-matches any prompt token (typo tolerance)."""
        for token in prompt_tokens:
            # Quick length check: if length diff > 30%, skip expensive comparison
            if abs(len(term) - len(token)) > max(len(term), len(token)) * 0.3:
                continue
            similarity = difflib.SequenceMatcher(None, term, token).ratio()
            if similarity >= self.fuzzy_threshold:
                return True
        return False

    def select(self, prompt: str, skills: list[Skill]) -> list[Skill]:  # noqa: D401
        """Return skills relevant to *prompt*."""
        prompt_tokens = _tokenize(prompt)
        prompt_lower = prompt.lower()

        always: list[Skill] = []
        scored: list[tuple[int, Skill]] = []

        for skill in skills:
            if skill.always:
                always.append(skill)
                continue

            score = 0

            # Resource types — high-signal structural match
            for rt in skill.resource_types:
                rt_lower = rt.lower()
                if rt_lower in prompt_lower:
                    score += 2
                elif self._fuzzy_match(rt_lower, prompt_tokens):
                    score += 1

            # Description + name — agentskills.io primary signal.
            # Tokenize once, score by overlap with prompt tokens.
            desc_tokens = _tokenize(skill.description) | _tokenize(skill.name.replace("-", " "))
            score += len(prompt_tokens & desc_tokens)

            # Fuzzy fallback: catch typos against high-signal description terms
            # the prompt didn't match exactly. Cap candidates to keep this O(N).
            if score == 0:
                for term in list(desc_tokens)[:40]:
                    if self._fuzzy_match(term, prompt_tokens):
                        score += 1
                        break

            scored.append((score, skill))

        selected = [skill for sc, skill in scored if sc >= self.min_score]

        if not selected:
            logger.debug("No skills matched prompt — falling back to all skills")
            return skills

        result = always + selected
        logger.info(
            "Selected %d/%d skills: %s",
            len(result),
            len(skills),
            ", ".join(s.name for s in result),
        )
        return result


# ── Helpers for embedding cache ─────────────────────────────────────────


def _skills_fingerprint(skills: list[Skill]) -> str:
    """Compute a stable hash of skill names + descriptions + resource types.

    Used to detect when the cached index needs to be rebuilt.
    """
    parts = [
        f"{s.name}:{s.description}:{','.join(s.resource_types)}"
        for s in sorted(skills, key=lambda s: s.name)
    ]
    content = "|".join(parts)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _skill_text(skill: Skill) -> str:
    """Build a rich text representation for embedding a single skill."""
    parts = [skill.name.replace("-", " "), skill.description]
    if skill.resource_types:
        parts.append(" ".join(skill.resource_types))
    return " ".join(parts)


# ── Semantic selector (default) ────────────────────────────────────────


class SemanticSelector:
    """Select skills by semantic similarity using local ONNX embeddings.

    Uses `fastembed <https://github.com/qdrant/fastembed>`_ for fast,
    PyTorch-free embeddings and :mod:`numpy` for cosine similarity.
    Embeddings are computed once and cached to
    ``~/.cache/fhir-synth/skills/`` keyed by model + fingerprint, so
    later loads read straight from disk in milliseconds.

    Selection logic:

    1. Skills with ``always=True`` are always included.
    2. Remaining skills are scored by cosine similarity (dot product of
       normalised vectors).
    3. Skills with score >= ``score_threshold`` are included, up to
       ``top_k`` of them.
    4. **Safe fallback**: if no skill clears the threshold, *all* skills
       are returned so behaviour is never worse than before skills existed.

    Args:
        model_name: fastembed model name.  Default
            ``"BAAI/bge-small-en-v1.5"`` — 384-dim, ~130 MB, strong on
            short-text retrieval.  Alternatives: ``"BAAI/bge-base-en-v1.5"``
            (768-dim, higher quality, ~440 MB).
        score_threshold: Minimum cosine similarity (0.0–1.0, default 0.5).
        top_k: Maximum number of skills to return above the threshold
            (default 5).
        cache_dir: Directory for cached embeddings.  Defaults to
            ``~/.cache/fhir-synth/skills/``.

    Example::

        selector = SemanticSelector()
        # First call: downloads model → encodes skills → saves to disk
        selected = selector.select("diabetes HbA1c labs", all_skills)

        # Second call: loads cached vectors (instant)
        selected = selector.select("coverage Medicare", all_skills)
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBED_MODEL,
        score_threshold: float = 0.5,
        top_k: int = 5,
        cache_dir: Path | None = None,
    ) -> None:
        self.model_name = model_name
        self.score_threshold = score_threshold
        self.top_k = top_k
        self.cache_dir = cache_dir or _DEFAULT_CACHE_DIR

        # Lazy state — model and vectors are loaded on first select()
        self._model: Any = None
        self._vectors: Any = None  # numpy.ndarray, shape (N, dim), L2-normalised
        self._indexed_skills: list[Skill] = []
        self._fingerprint: str = ""

    # ── Model loading ───────────────────────────────────────────────

    def _get_model(self) -> Any:
        """Lazy-load the fastembed TextEmbedding model."""
        if self._model is not None:
            return self._model
        from fastembed import TextEmbedding

        logger.debug("Loading embedding model: %s", self.model_name)
        self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    # ── Embedding ───────────────────────────────────────────────────

    def _embed(self, texts: list[str]) -> Any:
        """Embed *texts* with fastembed and return L2-normalised float32 array."""
        import numpy as np

        model = self._get_model()
        vectors = np.array(list(model.embed(texts)), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.maximum(norms, 1e-12)

    # ── Cache paths and persistence ─────────────────────────────────

    def _cache_paths(self, fingerprint: str) -> tuple[Path, Path]:
        """Return ``(vectors_path, meta_path)`` for a given fingerprint."""
        prefix = f"{self.model_name.replace('/', '_')}_{fingerprint}"
        return self.cache_dir / f"{prefix}.npy", self.cache_dir / f"{prefix}.json"

    def _save_index(self, fingerprint: str, skills: list[Skill]) -> None:
        """Persist vectors + metadata to disk for instant reload."""
        import numpy as np

        vectors_path, meta_path = self._cache_paths(fingerprint)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        np.save(vectors_path, self._vectors)
        meta = {
            "model": self.model_name,
            "fingerprint": fingerprint,
            "skills": [s.name for s in skills],
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info("Saved skill embeddings to %s (%d skills)", vectors_path, len(skills))

    def _load_index(self, fingerprint: str, skills: list[Skill]) -> bool:
        """Try to load cached vectors. Returns True on success."""
        import numpy as np

        vectors_path, meta_path = self._cache_paths(fingerprint)
        if not vectors_path.exists() or not meta_path.exists():
            return False

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.debug("Corrupt cache metadata at %s", meta_path)
            return False

        if meta.get("model") != self.model_name:
            return False
        if meta.get("fingerprint") != fingerprint:
            return False
        if meta.get("skills") != [s.name for s in skills]:
            return False

        try:
            self._vectors = np.load(vectors_path)
        except (OSError, ValueError):
            logger.debug("Could not load cached vectors at %s", vectors_path, exc_info=True)
            return False

        self._indexed_skills = list(skills)
        self._fingerprint = fingerprint
        logger.info("Loaded cached skill embeddings from %s (%d skills)", vectors_path, len(skills))
        return True

    # ── Index building ──────────────────────────────────────────────

    def _build_index(self, skills: list[Skill]) -> None:
        """Build or load the embedding index for *skills*."""
        fingerprint = _skills_fingerprint(skills)

        if self._load_index(fingerprint, skills):
            return

        texts = [_skill_text(s) for s in skills]
        logger.debug("Embedding %d skills with %s…", len(skills), self.model_name)
        self._vectors = self._embed(texts)
        self._indexed_skills = list(skills)
        self._fingerprint = fingerprint

        try:
            self._save_index(fingerprint, skills)
        except OSError:
            logger.warning("Could not cache embeddings to %s", self.cache_dir, exc_info=True)

    # ── Public API ──────────────────────────────────────────────────

    def select(self, prompt: str, skills: list[Skill]) -> list[Skill]:
        """Return semantically relevant skills for *prompt*.

        Always-on skills are included unconditionally.  Remaining skills
        are ranked by cosine similarity and filtered by ``score_threshold``
        and ``top_k``.  Falls back to all skills on error or empty result.
        """
        import numpy as np

        always = [s for s in skills if s.always]
        candidates = [s for s in skills if not s.always]

        if not candidates:
            return always

        fingerprint = _skills_fingerprint(candidates)
        if self._fingerprint != fingerprint:
            try:
                self._build_index(candidates)
            except Exception:
                logger.warning(
                    "Embedding index build failed — falling back to all skills",
                    exc_info=True,
                )
                return skills

        try:
            query_vec = self._embed([prompt])[0]
            scores = self._vectors @ query_vec
        except Exception:
            logger.warning("Semantic search failed — falling back to all skills", exc_info=True)
            return skills

        # Rank by score, filter by threshold and top_k
        ranked = np.argsort(scores)[::-1][: self.top_k]
        selected = [
            candidates[int(i)] for i in ranked if float(scores[int(i)]) >= self.score_threshold
        ]

        if not selected:
            logger.debug(
                "No skills above threshold %.2f — falling back to all", self.score_threshold
            )
            return skills

        result = always + selected
        logger.info(
            "Semantic selected %d/%d skills: %s (top scores: %s)",
            len(result),
            len(skills),
            ", ".join(s.name for s in result),
            ", ".join(f"{float(scores[int(i)]):.3f}" for i in ranked[: len(selected)]),
        )
        return result
