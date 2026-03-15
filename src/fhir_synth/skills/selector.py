"""Skill selection strategies.
Provides a: class:`SkillSelector` protocol and two concrete implementations:

*: class:`KeywordSelector` — zero-dependency keyword + resource-type matching
  with fuzzy matching for typo tolerance (default).
*: class:`FaissSelector` — semantic retrieval using ``faiss-cpu`` with
  ``sentence-transformers`` for local embeddings (no API calls).  Embeddings
  are pre-computed **once** and cached to disk, so later loads are
  instant.  Install with ``pip install fhir-synth[semantic]``.

Both return the Markdown bodies of the selected skills, ready for injection
into the LLM system prompt.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from fhir_synth.skills.loader import Skill

if TYPE_CHECKING:
    import types

logger = logging.getLogger(__name__)

# Default cache location for pre-computed FAISS index
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "fhir-synth" / "skills"

# Default local embedding model — good balance of quality / size / speed.
# all-MiniLM-L6-v2: 384-dim, 80 MB, very fast, top-tier for retrieval.
DEFAULT_EMBED_MODEL = "all-MiniLM-L6-v2"


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


# ── Keyword selector (default, zero deps) ──────────────────────────────


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
    """Select skills by keyword overlap between the prompt and skill metadata.

    Selection logic:

    1. Skills with ``always=True`` are always included.
    2. Each remaining skill is scored by counting how many of its
       ``keywords``, ``resource_types``, and description tokens appear in
       the prompt (with fuzzy matching for typo tolerance).
    3. Skills with score > 0 are included.
    4. **Safe fallback**: if no skill scored > 0, *all* skills are included
       so behaviour is never worse than before skills existed.

    Args:
        min_score: Minimum score for a skill to be selected (default 1).
        fuzzy_threshold: Similarity threshold for fuzzy matching (0.0-1.0, default 0.8).
            Lower = more tolerant of typos, higher = stricter matching.
    """

    def __init__(self, min_score: int = 1, fuzzy_threshold: float = 0.8) -> None:
        self.min_score = min_score
        self.fuzzy_threshold = fuzzy_threshold

    def _fuzzy_match(self, keyword: str, prompt_tokens: set[str]) -> bool:
        """Check if keyword fuzzy-matches any prompt token.

        Uses difflib.SequenceMatcher for typo tolerance.
        """
        for token in prompt_tokens:
            # Quick length check: if length diff > 30%, skip expensive comparison
            if abs(len(keyword) - len(token)) > max(len(keyword), len(token)) * 0.3:
                continue
            similarity = difflib.SequenceMatcher(None, keyword, token).ratio()
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

            # Match keywords (exact substring or fuzzy match)
            for kw in skill.keywords:
                kw_lower = kw.lower()
                if kw_lower in prompt_lower:
                    score += 2  # exact keyword hits are high-value
                elif self._fuzzy_match(kw_lower, prompt_tokens):
                    score += 1  # fuzzy match gets lower score

            # Match resource types (exact or fuzzy)
            for rt in skill.resource_types:
                rt_lower = rt.lower()
                if rt_lower in prompt_lower:
                    score += 2  # exact match
                elif self._fuzzy_match(rt_lower, prompt_tokens):
                    score += 1  # fuzzy match

            # Match description tokens against prompt tokens (exact only)
            desc_tokens = _tokenize(skill.description)
            score += len(prompt_tokens & desc_tokens)

            scored.append((score, skill))

        # Select skills above threshold
        selected = [skill for sc, skill in scored if sc >= self.min_score]

        if not selected:
            # Safe fallback: load everything (same as pre-skills behaviour)
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


# ── Helpers for FAISS index caching ─────────────────────────────────────


def _skills_fingerprint(skills: list[Skill]) -> str:
    """Compute a stable hash of skill names + descriptions.

    Used to detect when the index needs to be rebuilt (new/changed skills).
    """
    content = "|".join(f"{s.name}:{s.description}" for s in sorted(skills, key=lambda s: s.name))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _skill_text(skill: Skill) -> str:
    """Build a rich text representation for embedding a single skill."""
    parts = [skill.name.replace("-", " "), skill.description]
    if skill.keywords:
        parts.append(" ".join(skill.keywords))
    if skill.resource_types:
        parts.append(" ".join(skill.resource_types))
    return " ".join(parts)


# ── FAISS semantic selector ─────────────────────────────────────────────


class FaissSelector:
    """Select skills via semantic similarity with pre-computed embeddings.

    **Embeddings are generated once and cached to disk.**  Subsequent loads
    read the FAISS index + metadata from ``~/.cache/fhir-synth/skills/``
    in milliseconds — no model loading or API calls needed at query time
    after the first run.

    Uses `sentence-transformers <https://www.sbert.net/>`_ for local
    embeddings (default model: ``all-MiniLM-L6-v2``, 384-dim, ~80 MB)
    and raw ``faiss-cpu`` for the vector index.

    Install with::

        pip install fhir-synth[semantic]

    Args:
        model_name: sentence-transformers model name.
            Default ``"all-MiniLM-L6-v2"`` — fast, 384-dim, great for
            short-text retrieval.  Alternatives:
            ``"all-mpnet-base-v2"`` (768-dim, higher quality, slower).
        score_threshold: Minimum cosine similarity (0.0–1.0).
            Returns all skills above this threshold.
        cache_dir: Directory for the cached FAISS index and metadata.
            Defaults to ``~/.cache/fhir-synth/skills/``.

    Example::

        selector = FaissSelector()
        # First call: encodes skills → builds index → saves to disk
        selected = selector.select("diabetes HbA1c labs", all_skills)

        # Second call: loads index from disk (instant)
        selected = selector.select("coverage Medicare", all_skills)
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBED_MODEL,
        score_threshold: float = 0.3,
        cache_dir: Path | None = None,
    ) -> None:
        self.model_name = model_name
        self.score_threshold = score_threshold
        self.cache_dir = cache_dir or _DEFAULT_CACHE_DIR

        # Lazy state
        self._faiss: types.ModuleType | None = None
        self._np: types.ModuleType | None = None
        self._model: Any = None
        self._index: Any = None
        self._indexed_skills: list[Skill] = []
        self._fingerprint: str = ""

    # ── Dependency management ───────────────────────────────────────

    def _ensure_deps(self) -> tuple[Any, Any]:
        """Import faiss and numpy, raising a clear error if missing."""
        if self._faiss is not None and self._np is not None:
            return self._faiss, self._np
        try:
            import faiss  # type: ignore[import-untyped]
            import numpy as np
        except ImportError as exc:
            msg = (
                "FaissSelector requires faiss-cpu and numpy. "
                "Install with: pip install fhir-synth[semantic]  "
                "or: pip install faiss-cpu numpy"
            )
            raise ImportError(msg) from exc
        self._faiss = faiss
        self._np = np
        return faiss, np

    def _get_model(self) -> Any:
        """Lazy-load the sentence-transformers model."""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            msg = (
                "FaissSelector requires sentence-transformers. "
                "Install with: pip install fhir-synth[semantic]  "
                "or: pip install sentence-transformers"
            )
            raise ImportError(msg) from exc
        logger.debug("Loading embedding model: %s", self.model_name)
        self._model = SentenceTransformer(self.model_name)
        return self._model

    # ── Embedding ───────────────────────────────────────────────────

    def _embed(self, texts: list[str]) -> Any:
        """Embed texts using sentence-transformers (local, no API call).

        Returns:
            numpy array of shape (len(texts), dimension), dtype float32.
        """
        model = self._get_model()
        return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    # ── Index persistence (build once, load many) ───────────────────

    def _cache_paths(self, fingerprint: str) -> tuple[Path, Path]:
        """Return (index_path, meta_path) for a given fingerprint."""
        prefix = f"{self.model_name.replace('/', '_')}_{fingerprint}"
        index_path = self.cache_dir / f"{prefix}.faiss"
        meta_path = self.cache_dir / f"{prefix}.json"
        return index_path, meta_path

    def _save_index(
        self,
        fingerprint: str,
        skills: list[Skill],
    ) -> None:
        """Persist the FAISS index and skill metadata to disk."""
        faiss, _np = self._ensure_deps()
        index_path, meta_path = self._cache_paths(fingerprint)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self._index, str(index_path))

        meta = {
            "model": self.model_name,
            "fingerprint": fingerprint,
            "skills": [s.name for s in skills],
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info("Saved FAISS index to %s (%d skills)", index_path, len(skills))

    def _load_index(
        self,
        fingerprint: str,
        skills: list[Skill],
    ) -> bool:
        """Try to load a cached FAISS index from disk.

        Returns:
            ``True`` if a valid cached index was loaded, ``False`` otherwise.
        """
        faiss, _np = self._ensure_deps()
        index_path, meta_path = self._cache_paths(fingerprint)

        if not index_path.exists() or not meta_path.exists():
            return False

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.debug("Corrupt cache metadata at %s", meta_path)
            return False

        # Validate cache: same model, same fingerprint, same skill names
        if meta.get("model") != self.model_name:
            return False
        if meta.get("fingerprint") != fingerprint:
            return False
        cached_names = meta.get("skills", [])
        current_names = [s.name for s in skills]
        if cached_names != current_names:
            return False

        try:
            self._index = faiss.read_index(str(index_path))
        except Exception:
            logger.debug("Could not read FAISS index from %s", index_path, exc_info=True)
            return False

        self._indexed_skills = list(skills)
        self._fingerprint = fingerprint
        logger.info("Loaded cached FAISS index from %s (%d skills)", index_path, len(skills))
        return True

    # ── Index building ──────────────────────────────────────────────

    def _build_index(self, skills: list[Skill]) -> None:
        """Build (or load from cache) the FAISS index for skill retrieval."""
        faiss, np = self._ensure_deps()

        fingerprint = _skills_fingerprint(skills)

        # Try loading from disk cache first
        if self._load_index(fingerprint, skills):
            return

        # Build fresh: embed all skill texts
        texts = [_skill_text(s) for s in skills]
        logger.debug("Computing embeddings for %d skills with %s…", len(skills), self.model_name)
        matrix = self._embed(texts)
        matrix = np.array(matrix, dtype="float32")

        dimension = matrix.shape[1]
        self._index = faiss.IndexFlatIP(dimension)  # cosine on normalised vectors
        self._index.add(matrix)
        self._indexed_skills = list(skills)
        self._fingerprint = fingerprint

        # Persist to disk for next time
        try:
            self._save_index(fingerprint, skills)
        except OSError:
            logger.warning("Could not cache FAISS index to %s", self.cache_dir, exc_info=True)

    # ── Public API ──────────────────────────────────────────────────

    def select(self, prompt: str, skills: list[Skill]) -> list[Skill]:
        """Return semantically relevant skills for *prompt*.

        Always-on skills are included unconditionally.  Remaining skills are
        ranked by cosine similarity, returning all skills above the score
        threshold.  Falls back to all skills on error.
        """
        _faiss, np = self._ensure_deps()

        always = [s for s in skills if s.always]
        candidates = [s for s in skills if not s.always]

        if not candidates:
            return always

        # (Re)build index if skill set changed
        fingerprint = _skills_fingerprint(candidates)
        if self._fingerprint != fingerprint:
            try:
                self._build_index(candidates)
            except Exception:
                logger.warning(
                    "FAISS index build failed — falling back to all skills", exc_info=True
                )
                return skills

        # Embed query (fast: single sentence through local model)
        try:
            query_vec = self._embed([prompt])
            query_vec = np.array(query_vec, dtype="float32")

            # Search all candidates to get complete similarity scores
            k = len(candidates)
            scores, indices = self._index.search(query_vec, k)
        except Exception:
            logger.warning("FAISS search failed — falling back to all skills", exc_info=True)
            return skills

        # Filter by score threshold - return ALL skills above threshold
        selected: list[Skill] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue  # FAISS sentinel
            if float(score) >= self.score_threshold:
                selected.append(candidates[idx])

        if not selected:
            logger.debug(
                "No skills above threshold %.2f — falling back to all", self.score_threshold
            )
            return skills

        result = always + selected
        logger.info(
            "FAISS selected %d/%d skills: %s (top scores: %s)",
            len(result),
            len(skills),
            ", ".join(s.name for s in result),
            ", ".join(f"{s:.3f}" for s in scores[0][: min(5, len(selected))]),
        )
        return result
