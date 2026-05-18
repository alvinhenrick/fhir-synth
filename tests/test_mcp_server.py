"""Tests for the MCP server's skill-directory resolution.

Covers ``_resolve_skill_dirs`` and ``_file_uri_to_path`` — the helpers that
combine global, MCP-roots, and env-var sources into the list passed to
``SkillLoader``. The MCP tool entry points themselves call out to real LLMs
and aren't tested here.
"""

import asyncio
import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from fhir_synth.mcp import server


def _resolve(ctx: object) -> list[Path]:
    """Sync wrapper around the async ``_resolve_skill_dirs`` — avoids a pytest-asyncio dep."""
    return asyncio.run(server._resolve_skill_dirs(ctx))  # type: ignore[arg-type]


# ── _file_uri_to_path ────────────────────────────────────────────────────


def test_file_uri_to_path_basic() -> None:
    assert server._file_uri_to_path("file:///Users/alice/repo") == Path("/Users/alice/repo")


def test_file_uri_to_path_url_decoded() -> None:
    # Spaces in workspace paths come through as %20.
    assert server._file_uri_to_path("file:///tmp/My%20Project") == Path("/tmp/My Project")


def test_file_uri_to_path_non_file_scheme() -> None:
    assert server._file_uri_to_path("https://example.com/x") is None
    assert server._file_uri_to_path("not-a-uri") is None


# ── _resolve_skill_dirs ──────────────────────────────────────────────────


def _make_ctx_with_roots(mocker: MockerFixture, *uris: str) -> object:
    """Build a fake Context whose ``session.list_roots()`` returns the given URIs."""
    roots = [mocker.MagicMock(uri=u) for u in uris]
    result = mocker.MagicMock(roots=roots)
    ctx = mocker.MagicMock()
    ctx.session.list_roots = mocker.AsyncMock(return_value=result)
    return ctx


def _make_ctx_without_roots_support(mocker: MockerFixture) -> object:
    """Build a fake Context whose ``list_roots()`` raises (e.g. Claude Desktop)."""
    ctx = mocker.MagicMock()
    ctx.session.list_roots = mocker.AsyncMock(side_effect=RuntimeError("roots not supported"))
    return ctx


@pytest.fixture(autouse=True)
def _isolate_module_state(mocker: MockerFixture) -> None:
    """Default: no env-var override, no real global dirs. Tests opt in explicitly."""
    mocker.patch.object(server, "_SKILLS_DIR_ENV", "")
    mocker.patch.object(server, "_GLOBAL_SKILL_DIRS", ())


def test_resolve_empty_when_nothing_configured() -> None:
    assert _resolve(ctx=None) == []


def test_resolve_global_dir_when_it_exists(tmp_path: Path, mocker: MockerFixture) -> None:
    global_dir = tmp_path / "global_skills"
    global_dir.mkdir()
    mocker.patch.object(server, "_GLOBAL_SKILL_DIRS", (global_dir,))

    assert _resolve(ctx=None) == [global_dir.resolve()]


def test_resolve_skips_global_dir_that_does_not_exist(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    mocker.patch.object(server, "_GLOBAL_SKILL_DIRS", (tmp_path / "missing",))
    assert _resolve(ctx=None) == []


def test_resolve_discovers_both_root_subdirs(tmp_path: Path, mocker: MockerFixture) -> None:
    root = tmp_path / "workspace"
    claude_dir = root / ".claude" / "skills"
    dot_skills_dir = root / ".skills"
    claude_dir.mkdir(parents=True)
    dot_skills_dir.mkdir(parents=True)

    ctx = _make_ctx_with_roots(mocker, f"file://{root}")
    dirs = _resolve(ctx)

    assert set(dirs) == {claude_dir.resolve(), dot_skills_dir.resolve()}


def test_resolve_skips_root_subdirs_that_dont_exist(tmp_path: Path, mocker: MockerFixture) -> None:
    root = tmp_path / "empty_workspace"
    root.mkdir()
    ctx = _make_ctx_with_roots(mocker, f"file://{root}")
    assert _resolve(ctx) == []


def test_resolve_gracefully_handles_client_without_roots(mocker: MockerFixture) -> None:
    # Client raises on roots/list — must not propagate; just yields no root dirs.
    ctx = _make_ctx_without_roots_support(mocker)
    assert _resolve(ctx) == []


def test_resolve_ignores_non_file_root_uris(mocker: MockerFixture) -> None:
    ctx = _make_ctx_with_roots(mocker, "https://example.com/repo")
    assert _resolve(ctx) == []


def test_resolve_env_var_entries(tmp_path: Path, mocker: MockerFixture) -> None:
    extra = tmp_path / "extra"
    extra.mkdir()
    mocker.patch.object(server, "_SKILLS_DIR_ENV", str(extra))

    assert _resolve(ctx=None) == [extra.resolve()]


def test_resolve_env_var_supports_multiple_paths(tmp_path: Path, mocker: MockerFixture) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    mocker.patch.object(server, "_SKILLS_DIR_ENV", f"{a}{os.pathsep}{b}")

    assert _resolve(ctx=None) == [a.resolve(), b.resolve()]


def test_resolve_priority_order_global_then_roots_then_env(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    # All three sources distinct — verify the documented ordering survives end to end.
    global_dir = tmp_path / "global"
    root_dir = tmp_path / "workspace"
    root_claude = root_dir / ".claude" / "skills"
    env_dir = tmp_path / "env"
    global_dir.mkdir()
    root_claude.mkdir(parents=True)
    env_dir.mkdir()

    mocker.patch.object(server, "_GLOBAL_SKILL_DIRS", (global_dir,))
    mocker.patch.object(server, "_SKILLS_DIR_ENV", str(env_dir))
    ctx = _make_ctx_with_roots(mocker, f"file://{root_dir}")

    dirs = _resolve(ctx)
    assert dirs == [global_dir.resolve(), root_claude.resolve(), env_dir.resolve()]


def test_resolve_deduplicates_overlap_between_sources(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    # Same dir reachable through env *and* a root — must appear exactly once.
    root = tmp_path / "workspace"
    shared = root / ".claude" / "skills"
    shared.mkdir(parents=True)

    mocker.patch.object(server, "_SKILLS_DIR_ENV", str(shared))
    ctx = _make_ctx_with_roots(mocker, f"file://{root}")

    dirs = _resolve(ctx)
    assert dirs == [shared.resolve()]
