"""Tests for science_tool.commons.cli — promote subgroup."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner
from test_commons_promote_apply import _init_commons


def _bare_project_from_fixture(tmp_path: Path, fixture_name: str, slug: str) -> Path:
    """Copy a fixture project into tmp_path and init a git repo."""
    src = Path(__file__).parent / "fixtures" / "promote" / fixture_name
    dst = tmp_path / slug
    shutil.copytree(src, dst)
    subprocess.run(["git", "init", "-q", str(dst)], check=True)
    subprocess.run(["git", "-C", str(dst), "config", "user.email", "test@x"], check=True)
    subprocess.run(["git", "-C", str(dst), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(dst), "add", "."], check=True)
    subprocess.run(["git", "-C", str(dst), "commit", "-q", "-m", "init"], check=True)
    return dst


@pytest.fixture
def runner():
    return CliRunner()


def test_promote_paper_bulk_dry_run_summary(tmp_path, monkeypatch, runner) -> None:
    from science_tool.commons.cli import commons_group

    _init_commons(tmp_path / "commons")
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    beta = _bare_project_from_fixture(tmp_path, "proj-beta", "proj-beta")

    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: {"proj-alpha": alpha, "proj-beta": beta}[slug],
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.prompt_resolve",
        lambda conflict: sorted(conflict.candidates.items())[0][1],
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "proj-alpha", "--from", "proj-beta"],
    )
    assert result.exit_code == 0, result.output
    assert "Discovered" in result.output
    assert "single-instance" in result.output
    assert "Adams2025" in result.output or "4 single-instance" in result.output
    assert not (tmp_path / "commons" / "papers" / "Adams2025.md").exists()


def test_promote_paper_limit_zero_reports_full_count_and_stops(tmp_path, monkeypatch, runner) -> None:
    """`--limit 0` is a discovery-only summary: it must report the FULL discovered
    count (not 0) and stop before planning/applying."""
    from science_tool.commons.cli import commons_group

    _init_commons(tmp_path / "commons")
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    beta = _bare_project_from_fixture(tmp_path, "proj-beta", "proj-beta")

    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: {"proj-alpha": alpha, "proj-beta": beta}[slug],
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "proj-alpha", "--from", "proj-beta", "--limit", "0"],
    )
    assert result.exit_code == 0, result.output
    # Regression: the old code truncated candidates to empty before counting,
    # so this said "Discovered 0 paper candidates". It must now report the real count.
    assert "Discovered 0 paper candidates" not in result.output
    assert "single-instance" in result.output
    assert "Discovery-only" in result.output
    # Stopped before planning and writing.
    assert "Plan:" not in result.output
    assert not (tmp_path / "commons" / "papers" / "Adams2025.md").exists()


def test_promote_paper_apply_writes_and_tags(tmp_path, monkeypatch, runner) -> None:
    from science_tool.commons.cli import commons_group

    _init_commons(tmp_path / "commons")
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: alpha,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.prompt_resolve",
        lambda conflict: sorted(conflict.candidates.items())[0][1],
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "proj-alpha", "--apply"],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "commons" / "papers" / "Adams2025.md").exists()
    tags = subprocess.run(
        ["git", "-C", str(tmp_path / "commons"), "tag"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert "paper/Adams2025/1.0.0" in tags


def test_promote_paper_null_id_exits_nonzero(tmp_path, monkeypatch, runner) -> None:
    from science_tool.commons.cli import commons_group
    from science_tool.commons.errors import CommonsError

    _init_commons(tmp_path / "commons")
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: (_ for _ in ()).throw(CommonsError(f"{slug!r} has id: null")),
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "legacy-slug"],
    )
    assert result.exit_code != 0
    assert "id: null" in result.output


def test_promote_paper_missing_commons_exits_nonzero(tmp_path, monkeypatch, runner) -> None:
    from science_tool.commons.cli import commons_group

    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "no-commons",
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "proj-alpha"],
    )
    assert result.exit_code != 0
    assert "science commons init" in result.output


def test_promote_paper_single_entity_form(tmp_path, monkeypatch, runner) -> None:
    from science_tool.commons.cli import commons_group

    _init_commons(tmp_path / "commons")
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: alpha,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "paper:Adams2025", "--from", "proj-alpha"],
    )
    assert result.exit_code == 0, result.output
    assert "Adams2025" in result.output


def test_promote_paper_apply_reindexes_registry(tmp_path, monkeypatch, runner) -> None:
    """After --apply, the CLI must rebuild registry.sqlite so it is not stale (t063 fb-002)."""
    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.cli import commons_group
    from science_tool.commons.registry import RegistryBuilder

    commons_root = tmp_path / "commons"
    _init_commons(commons_root)
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: alpha,
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: commons_root,
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.prompt_resolve",
        lambda conflict: sorted(conflict.candidates.items())[0][1],
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "proj-alpha", "--apply"],
    )
    assert result.exit_code == 0, result.output
    # CLI must emit the reindex line.
    assert "Reindexed commons registry:" in result.output
    # Registry must not be stale immediately after the CLI apply.
    builder = RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root))
    assert not builder.is_stale(), "registry.sqlite should be fresh after CLI --apply"


def test_promote_paper_plan_time_collision_exits_nonzero_cleanly(
    tmp_path, monkeypatch, runner,
) -> None:
    """plan_promote can raise PromoteInputError on a case-rename collision
    BEFORE any disk write. The CLI must catch it and return a clean Click
    error (non-zero exit, helpful message) — never an unhandled traceback."""
    from science_tool.commons.cli import commons_group

    _init_commons(tmp_path / "commons")

    def _init_proj(proj: Path) -> None:
        subprocess.run(["git", "init", "-q", str(proj)], check=True)
        subprocess.run(["git", "-C", str(proj), "config", "user.email", "t@x"], check=True)
        subprocess.run(["git", "-C", str(proj), "config", "user.name", "t"], check=True)
        subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
        subprocess.run(["git", "-C", str(proj), "commit", "-q", "-m", "init"], check=True)

    # proj-a fixes the canonical case to `Huh2024` via --from ordering.
    proj_a = tmp_path / "proj-a"
    (proj_a / "entities" / "papers").mkdir(parents=True)
    (proj_a / "entities" / "papers" / "Huh2024.md").write_text(
        "---\nid: paper:Huh2024\ntitle: H1\n---\n", encoding="utf-8",
    )
    _init_proj(proj_a)

    # proj-b carries `huh2024.md`, which must rename to `Huh2024.md`, but a stale
    # file already occupies that canonical-case overlay target.
    proj_b = tmp_path / "proj-b"
    (proj_b / "entities" / "papers").mkdir(parents=True)
    (proj_b / "entities" / "papers" / "huh2024.md").write_text(
        "---\nid: paper:huh2024\ntitle: H2\n---\n", encoding="utf-8",
    )
    (proj_b / "overlays" / "papers").mkdir(parents=True)
    (proj_b / "overlays" / "papers" / "Huh2024.md").write_text(
        "---\nid: paper:Huh2024\ntitle: stale\n---\n", encoding="utf-8",
    )
    _init_proj(proj_b)

    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: {"proj-a": proj_a, "proj-b": proj_b}[slug],
    )
    monkeypatch.setattr(
        "science_tool.commons.cli.resolve_commons_root",
        lambda: tmp_path / "commons",
    )

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "--from", "proj-a", "--from", "proj-b"],
    )
    assert result.exit_code != 0
    assert "case-rename collision" in result.output
    assert "Traceback" not in result.output
