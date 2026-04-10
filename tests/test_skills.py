"""Tests for the skills system — loader, selector, and prompt integration."""

import textwrap
from pathlib import Path

import pytest

from fhir_synth.skills.loader import Skill, SkillLoader, _parse_skill_md
from fhir_synth.skills.selector import KeywordSelector

# ── Fixtures ────────────────────────────────────────────────────────────


SAMPLE_SKILL_MD = textwrap.dedent("""\
    ---
    name: test-skill
    description: A test skill for unit testing. Use when user mentions testing or pytest.
    keywords: [testing, pytest, unit test]
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
    keywords: [patient, demographic]
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


# ── _parse_skill_md ────────────────────────────────────────────────────


def test_parse_full_skill() -> None:
    skill = _parse_skill_md(SAMPLE_SKILL_MD, "/fake/SKILL.md")
    assert skill is not None
    assert skill.name == "test-skill"
    assert "unit testing" in skill.description
    assert skill.keywords == ["testing", "pytest", "unit test"]
    assert skill.resource_types == ["Patient", "Observation"]
    assert skill.always is False
    assert "Rule 1" in skill.body


def test_parse_minimal_skill() -> None:
    skill = _parse_skill_md(MINIMAL_SKILL_MD, "/fake/SKILL.md")
    assert skill is not None
    assert skill.name == "minimal"
    assert skill.keywords == []
    assert skill.resource_types == []
    assert skill.always is False


def test_parse_always_on_skill() -> None:
    skill = _parse_skill_md(ALWAYS_SKILL_MD, "/fake/SKILL.md")
    assert skill is not None
    assert skill.always is True


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
        # Clear builtin cache to isolate test
        skills = loader.discover()
        user_skills = [s for s in skills if s.source == "user"]
        assert any(s.name == "test-skill" for s in user_skills)

    def test_discover_empty_dir(self, tmp_path: Path) -> None:
        """Empty directory should not crash."""
        loader = SkillLoader(user_dirs=[tmp_path])
        skills = loader.discover()
        # Should still find built-in skills (if any) but not crash
        assert isinstance(skills, list)

    def test_discover_nonexistent_dir(self) -> None:
        """Non-existent directory should not crash."""
        loader = SkillLoader(user_dirs=[Path("/nonexistent/path")])
        skills = loader.discover()
        assert isinstance(skills, list)

    def test_user_overrides_builtin(self, tmp_path: Path) -> None:
        """User skill with same name as built-in should override it."""
        # Create a user skill named "patient-variation" (same as built-in)
        skill_dir = tmp_path / "patient-variation"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            textwrap.dedent("""\
            ---
            name: patient-variation
            description: User override for patient variation.
            keywords: [patient]
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
    """Tests for keyword-based skill selection."""

    @pytest.fixture()
    def skills(self) -> list[Skill]:
        """Sample skill list for selection tests."""
        return [
            Skill(
                name="patient-variation",
                description="Patient demographics and diversity.",
                body="Patient body",
                keywords=["patient", "demographic", "age", "gender"],
                resource_types=["Patient"],
                always=True,
            ),
            Skill(
                name="medications",
                description="Medication prescriptions with RxNorm codes.",
                body="Medications body",
                keywords=["medication", "prescription", "drug", "pharmacy", "RxNorm"],
                resource_types=["MedicationRequest"],
                always=False,
            ),
            Skill(
                name="vitals-and-labs",
                description="Vital signs and lab panels with LOINC codes.",
                body="Vitals body",
                keywords=["vital", "lab", "observation", "blood pressure", "HbA1c", "glucose"],
                resource_types=["Observation"],
                always=False,
            ),
            Skill(
                name="coverage",
                description="Coverage and insurance with payer diversity.",
                body="Coverage body",
                keywords=["coverage", "insurance", "payer", "Medicare", "Medicaid"],
                resource_types=["Coverage"],
                always=False,
            ),
            Skill(
                name="comorbidity",
                description="Comorbidity patterns with disease clustering.",
                body="Comorbidity body",
                keywords=["comorbidity", "condition", "diagnosis", "diabetes", "hypertension"],
                resource_types=["Condition"],
                always=False,
            ),
        ]

    def test_always_on_included(self, skills: list[Skill]) -> None:
        selector = KeywordSelector()
        result = selector.select("diabetes medications", skills)
        names = [s.name for s in result]
        assert "patient-variation" in names  # always=True

    def test_keyword_match(self, skills: list[Skill]) -> None:
        selector = KeywordSelector()
        result = selector.select("10 patients with diabetes medications", skills)
        names = [s.name for s in result]
        assert "medications" in names
        assert "comorbidity" in names  # "diabetes" keyword

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

    def test_multi_keyword_match(self, skills: list[Skill]) -> None:
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
        """Typos in keywords should still match via fuzzy matching."""
        selector = KeywordSelector(fuzzy_threshold=0.8)
        # "medicaton" is close to "medication" (80% similarity)
        result = selector.select("10 patients with diabtes and medicaton", skills)
        names = [s.name for s in result]
        assert "medications" in names  # should match despite typo
        assert "comorbidity" in names  # "diabtes" close to "diabetes"

    def test_fuzzy_match_threshold(self, skills: list[Skill]) -> None:
        """Very different words should not match even with fuzzy matching."""
        selector = KeywordSelector(fuzzy_threshold=0.8)
        # "xyzzy" is not similar to any keyword
        result = selector.select("10 patients with xyzzy foobar", skills)
        # Should fallback to all skills since nothing matched
        assert len(result) == len(skills)

    def test_exact_match_scores_higher_than_fuzzy(self, skills: list[Skill]) -> None:
        """Exact keyword matches should score higher than fuzzy matches."""
        selector = KeywordSelector(min_score=2, fuzzy_threshold=0.8)
        # "medication" exact match should score 2, fuzzy match only scores 1
        result = selector.select("10 patients with medication", skills)
        names = [s.name for s in result]
        assert "medications" in names

        # Fuzzy match alone (score=1) won't meet min_score=2 threshold
        result2 = selector.select("10 patients with medicaton", skills)
        # Should fallback to all skills
        assert len(result2) == len(skills)


# ── Built-in skills discovery ────────────────────────────────────────


class TestBuiltinSkills:
    """Verify that the built-in skills ship correctly."""

    def test_builtin_skills_exist(self) -> None:
        loader = SkillLoader()
        skills = loader.discover()
        assert len(skills) >= 11  # we have 13 built-in skills

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
        assert len(always_on) >= 3  # patient-variation + edge-cases + provenance-data-quality
        always_names = {s.name for s in always_on}
        assert "patient-variation" in always_names
        assert "edge-cases" in always_names
        assert "provenance-data-quality" in always_names

    def test_all_builtin_are_builtin_source(self) -> None:
        loader = SkillLoader()
        skills = loader.discover()
        for skill in skills:
            assert skill.source == "builtin"
