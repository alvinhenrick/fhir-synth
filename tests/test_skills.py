"""Tests for the skills system — loader, selector, and prompt integration."""

import textwrap
from pathlib import Path

import pytest

from fhir_synth.skills.loader import Skill, SkillLoader, _parse_skill_md
from fhir_synth.skills.selector import KeywordSelector

# ── Fixtures ────────────────────────────────────────────────────────────

# Per the agentskills.io spec, `description` is the selection signal.
# Sample frontmatter mirrors that — no `keywords:` field.

SAMPLE_SKILL_MD = textwrap.dedent("""\
    ---
    name: test-skill
    description: A test skill for unit testing. Use when user mentions testing or pytest.
    resource_types: [Patient, Observation]
    always: false
    ---

    # Test Skill

    This is the body of the test skill.
    - Rule 1
    - Rule 2
""")

ALWAYS_SKILL_MD = textwrap.dedent("""\
    ---
    name: always-on
    description: Always included skill for patient demographics.
    resource_types: [Patient]
    always: true
    ---

    Always-on body content.
""")

MINIMAL_SKILL_MD = textwrap.dedent("""\
    ---
    name: minimal
    description: Minimal skill with only required fields.
    ---

    Minimal body.
""")

# Legacy file with `keywords:` — confirms backward-compat (loader ignores it).
LEGACY_KEYWORDS_SKILL_MD = textwrap.dedent("""\
    ---
    name: legacy-keywords
    description: Legacy skill that still declares a keywords field.
    keywords: [legacy, ignored, deprecated]
    resource_types: [Patient]
    ---

    Legacy body.
""")


# ── _parse_skill_md ────────────────────────────────────────────────────


def test_parse_full_skill() -> None:
    skill = _parse_skill_md(SAMPLE_SKILL_MD, "/fake/SKILL.md")
    assert skill is not None
    assert skill.name == "test-skill"
    assert "unit testing" in skill.description
    assert skill.resource_types == ["Patient", "Observation"]
    assert skill.always is False
    assert "Rule 1" in skill.body


def test_parse_minimal_skill() -> None:
    skill = _parse_skill_md(MINIMAL_SKILL_MD, "/fake/SKILL.md")
    assert skill is not None
    assert skill.name == "minimal"
    assert skill.resource_types == []
    assert skill.always is False


def test_parse_always_on_skill() -> None:
    skill = _parse_skill_md(ALWAYS_SKILL_MD, "/fake/SKILL.md")
    assert skill is not None
    assert skill.always is True


def test_parse_legacy_keywords_field_is_ignored() -> None:
    """SKILL.md files with legacy `keywords:` should still parse cleanly."""
    skill = _parse_skill_md(LEGACY_KEYWORDS_SKILL_MD, "/fake/SKILL.md")
    assert skill is not None
    assert skill.name == "legacy-keywords"
    assert not hasattr(skill, "keywords")


def test_parse_no_frontmatter() -> None:
    result = _parse_skill_md("# Just markdown\nNo frontmatter here.", "/fake/SKILL.md")
    assert result is None


def test_parse_missing_name() -> None:
    content = "---\ndescription: No name field\n---\nBody."
    result = _parse_skill_md(content, "/fake/SKILL.md")
    assert result is None


def test_parse_missing_description() -> None:
    content = "---\nname: no-desc\n---\nBody."
    result = _parse_skill_md(content, "/fake/SKILL.md")
    assert result is None


def test_parse_invalid_yaml() -> None:
    content = "---\n: invalid: yaml: [[\n---\nBody."
    result = _parse_skill_md(content, "/fake/SKILL.md")
    assert result is None


def test_parse_source_label() -> None:
    skill = _parse_skill_md(SAMPLE_SKILL_MD, "/fake/SKILL.md", source="user")
    assert skill is not None
    assert skill.source == "user"


# ── SkillLoader (filesystem discovery) ──────────────────────────────────


class TestSkillLoader:
    """Tests for skill discovery from directories."""

    def test_discover_from_user_dir(self, tmp_path: Path) -> None:
        """Create a skill in a temp dir and verify discovery."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(SAMPLE_SKILL_MD)

        loader = SkillLoader(user_dirs=[tmp_path])
        skills = loader.discover()
        user_skills = [s for s in skills if s.source == "user"]
        assert any(s.name == "test-skill" for s in user_skills)

    def test_discover_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory should not crash."""
        loader = SkillLoader(user_dirs=[tmp_path])
        skills = loader.discover()
        assert isinstance(skills, list)

    def test_discover_nonexistent_dir(self) -> None:
        """Non-existent directory should not crash."""
        loader = SkillLoader(user_dirs=[Path("/nonexistent/path")])
        skills = loader.discover()
        assert isinstance(skills, list)

    def test_user_overrides_builtin(self, tmp_path: Path) -> None:
        """User skill with same name as built-in should override it."""
        skill_dir = tmp_path / "patient-variation"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            textwrap.dedent("""\
            ---
            name: patient-variation
            description: User override for patient variation.
            resource_types: [Patient]
            always: true
            ---

            User-provided patient variation body.
        """)
        )

        loader = SkillLoader(user_dirs=[tmp_path])
        skills = loader.discover()
        pv = [s for s in skills if s.name == "patient-variation"]
        assert len(pv) == 1
        assert pv[0].source == "user"
        assert "User-provided" in pv[0].body

    def test_discover_caches(self, tmp_path: Path) -> None:
        """Repeated discover() calls should return cached results."""
        loader = SkillLoader(user_dirs=[tmp_path])
        result1 = loader.discover()
        result2 = loader.discover()
        assert result1 is result2

    def test_reset_clears_cache(self, tmp_path: Path) -> None:
        """reset() should force re-discovery."""
        loader = SkillLoader(user_dirs=[tmp_path])
        result1 = loader.discover()
        loader.reset()
        result2 = loader.discover()
        assert result1 is not result2


# ── KeywordSelector ─────────────────────────────────────────────────────


class TestKeywordSelector:
    """Tests for description-driven skill selection (agentskills.io spec)."""

    @pytest.fixture()
    def skills(self) -> list[Skill]:
        """Sample skill list mirroring real SKILL.md descriptions — trigger
        terms (medication, RxNorm, HbA1c, Medicare, diabetes, etc.) live in
        the description, since that is the selection signal in the spec.
        """
        return [
            Skill(
                name="patient-variation",
                description=(
                    "Patient demographics and diversity — age, gender, race, "
                    "ethnicity, language. Use when user mentions patient, "
                    "demographic, neonatal, pediatric, geriatric, or elderly."
                ),
                body="Patient body",
                resource_types=["Patient"],
                always=True,
            ),
            Skill(
                name="medications",
                description=(
                    "Medication prescriptions with RxNorm codes, dosage, route, "
                    "and polypharmacy. Use when user mentions medication, "
                    "prescription, drug, pharmacy, RxNorm, insulin, or metformin."
                ),
                body="Medications body",
                resource_types=["MedicationRequest"],
                always=False,
            ),
            Skill(
                name="vitals-and-labs",
                description=(
                    "Vital signs and lab panels with LOINC codes. Use when user "
                    "mentions vital, lab, observation, blood pressure, HbA1c, or "
                    "glucose."
                ),
                body="Vitals body",
                resource_types=["Observation"],
                always=False,
            ),
            Skill(
                name="coverage",
                description=(
                    "Coverage and insurance with payer diversity. Use when user "
                    "mentions coverage, insurance, payer, Medicare, or Medicaid."
                ),
                body="Coverage body",
                resource_types=["Coverage"],
                always=False,
            ),
            Skill(
                name="comorbidity",
                description=(
                    "Comorbidity patterns with disease clustering. Use when user "
                    "mentions comorbidity, condition, diagnosis, diabetes, "
                    "hypertension, COPD, or heart failure."
                ),
                body="Comorbidity body",
                resource_types=["Condition"],
                always=False,
            ),
        ]

    def test_always_on_included(self, skills: list[Skill]) -> None:
        selector = KeywordSelector()
        result = selector.select("diabetes medications", skills)
        names = [s.name for s in result]
        assert "patient-variation" in names  # always=True

    def test_description_term_match(self, skills: list[Skill]) -> None:
        selector = KeywordSelector()
        result = selector.select("10 patients with diabetes medications", skills)
        names = [s.name for s in result]
        assert "medications" in names
        assert "comorbidity" in names  # "diabetes" appears in description

    def test_resource_type_match(self, skills: list[Skill]) -> None:
        selector = KeywordSelector()
        result = selector.select("Generate Observation resources", skills)
        names = [s.name for s in result]
        assert "vitals-and-labs" in names

    def test_no_match_fallback(self, skills: list[Skill]) -> None:
        """When nothing matches, all skills should be returned (safe fallback)."""
        selector = KeywordSelector()
        result = selector.select("xyzzy foobar", skills)
        assert len(result) == len(skills)

    def test_coverage_not_selected_for_diabetes(self, skills: list[Skill]) -> None:
        selector = KeywordSelector()
        result = selector.select("5 patients with diabetes", skills)
        names = [s.name for s in result]
        assert "coverage" not in names

    def test_coverage_selected_for_insurance(self, skills: list[Skill]) -> None:
        selector = KeywordSelector()
        result = selector.select("patients with Medicare insurance", skills)
        names = [s.name for s in result]
        assert "coverage" in names

    def test_multi_domain_match(self, skills: list[Skill]) -> None:
        """Prompt mentioning multiple domains selects multiple skills."""
        selector = KeywordSelector()
        result = selector.select(
            "elderly patients with diabetes, medications, and lab results", skills
        )
        names = [s.name for s in result]
        assert "medications" in names
        assert "vitals-and-labs" in names
        assert "comorbidity" in names

    def test_fuzzy_match_typo(self, skills: list[Skill]) -> None:
        """Typos should still match via fuzzy matching against description tokens."""
        selector = KeywordSelector(fuzzy_threshold=0.85)
        # "medicaton" is close to "medication" (in the description)
        result = selector.select("10 patients with medicaton", skills)
        names = [s.name for s in result]
        assert "medications" in names

    def test_fuzzy_match_threshold(self, skills: list[Skill]) -> None:
        """Very different words should not match even with fuzzy matching."""
        selector = KeywordSelector(fuzzy_threshold=0.85)
        result = selector.select("10 patients with xyzzy foobar", skills)
        # Should fall back to all skills since nothing matched
        assert len(result) == len(skills)


# ── Built-in skills discovery ────────────────────────────────────────


class TestBuiltinSkills:
    """Verify that the built-in skills ship correctly."""

    def test_builtin_skills_exist(self) -> None:
        loader = SkillLoader()
        skills = loader.discover()
        assert len(skills) >= 11

    def test_builtin_skills_have_bodies(self) -> None:
        loader = SkillLoader()
        skills = loader.discover()
        for skill in skills:
            assert skill.body, f"Skill {skill.name} has empty body"
            assert skill.description, f"Skill {skill.name} has empty description"

    def test_always_on_skills_exist(self) -> None:
        loader = SkillLoader()
        skills = loader.discover()
        always_on = [s for s in skills if s.always]
        assert len(always_on) >= 3
        always_names = {s.name for s in always_on}
        assert "patient-variation" in always_names
        assert "edge-cases" in always_names
        assert "provenance-data-quality" in always_names

    def test_all_builtin_are_builtin_source(self) -> None:
        loader = SkillLoader()
        skills = loader.discover()
        for skill in skills:
            assert skill.source == "builtin"
