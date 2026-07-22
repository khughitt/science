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


@pytest.fixture(autouse=True)
def _isolate_registered_projects(monkeypatch):
    """No promote test may read the developer's real ~/.config global config.

    The federation guard enumerates registered projects; default it to empty so
    each test declares its own federation explicitly.
    """
    from science_tool.registry.config import GlobalConfig

    monkeypatch.setattr(
        "science_tool.registry.config.load_global_config",
        lambda *a, **k: GlobalConfig(projects=[]),
    )


def _register_bystander(monkeypatch, name: str, root: Path) -> None:
    from datetime import date

    from science_tool.registry.config import GlobalConfig, RegisteredProject

    config = GlobalConfig(
        projects=[RegisteredProject(path=str(root), name=name, registered=date(2026, 1, 1), id=name)]
    )
    monkeypatch.setattr("science_tool.registry.config.load_global_config", lambda *a, **k: config)


def _bystander_owning(tmp_path: Path, name: str, slug: str, *, doi: str, title: str) -> Path:
    root = tmp_path / name
    papers = root / "entities" / "papers"
    papers.mkdir(parents=True)
    papers.joinpath(f"{slug}.md").write_text(
        f"---\nid: paper:{slug}\nkind: paper\ntitle: {title}\ndoi: {doi}\n---\n\n## Key Findings\n\nx\n",
        encoding="utf-8",
    )
    return root


def test_promote_refuses_when_it_would_shadow_a_distinct_paper(tmp_path, monkeypatch, runner) -> None:
    """fb-2026-07-11-018: minting paper:Adams2025 must not shadow a different Adams2025."""
    from science_tool.commons.cli import commons_group

    commons = tmp_path / "commons"
    _init_commons(commons)
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    bystander = _bystander_owning(
        tmp_path, "natural-systems", "Adams2025", doi="10.9/different", title="A different paper"
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: {"proj-alpha": alpha}[slug],
    )
    monkeypatch.setattr("science_tool.commons.cli.registry_root_for_id", lambda slug: alpha)
    monkeypatch.setattr("science_tool.commons.cli.resolve_commons_root", lambda: commons)
    _register_bystander(monkeypatch, "natural-systems", bystander)

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "paper:Adams2025", "--from", "proj-alpha", "--apply"],
    )

    assert result.exit_code != 0, result.output
    assert "shadow" in result.output.lower()
    assert "natural-systems" in result.output
    assert "No writes" in result.output
    # Fail-closed: nothing was written to commons.
    assert not (commons / "papers" / "Adams2025.md").exists()


def test_promote_refuses_paper_with_uncopromotable_dataset_usage(tmp_path, monkeypatch, runner) -> None:
    """fb-2026-07-19-005: a paper whose dataset_usage points at a dataset with no
    commons canonical must be refused — promoting it would mint a dangling ref in
    the shared store that every consumer of the paper then hard-errors on."""
    from science_tool.commons.cli import commons_group

    commons = tmp_path / "commons"
    _init_commons(commons)
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    # A paper referencing a reference-only cohort that is not (and cannot be) a
    # commons canonical.
    alpha.joinpath("entities", "papers", "Kotliarov2020.md").write_text(
        "---\nid: paper:Kotliarov2020\nkind: paper\ntitle: Kotliarov 2020\n"
        "authors:\n  - Kotliarov, Y.\nyear: 2020\nvenue: Nat Med\ndoi: 10.1/kotliarov\n"
        'created: "2026-01-01"\nupdated: "2026-02-01"\n'
        "dataset_usage:\n  - ref: dataset:websle-paediatric-sle\n    role: analyzed\n"
        "---\n\n## Key Findings\n\nx\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: {"proj-alpha": alpha}[slug],
    )
    monkeypatch.setattr("science_tool.commons.cli.registry_root_for_id", lambda slug: alpha)
    monkeypatch.setattr("science_tool.commons.cli.resolve_commons_root", lambda: commons)

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "paper:Kotliarov2020", "--from", "proj-alpha", "--apply"],
    )

    assert result.exit_code != 0, result.output
    assert "dataset:websle-paediatric-sle" in result.output
    assert "dataset_usage" in result.output
    assert not (commons / "papers" / "Kotliarov2020.md").exists()


def test_promote_paper_warns_on_missing_evidential_sections(tmp_path, monkeypatch, runner) -> None:
    """fb-2026-07-11-020: a paper canonical with no Methods/Limitations is warned
    about at promote time (dry run) — consumers cannot assess evidential strength.
    The warning does not block: exit stays 0 on a clean dry run."""
    from science_tool.commons.cli import commons_group

    commons = tmp_path / "commons"
    _init_commons(commons)
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    # proj-alpha's Adams2025 carries "Key Findings" + "Project Use" but no
    # Methods or Limitations section.

    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: {"proj-alpha": alpha}[slug],
    )
    monkeypatch.setattr("science_tool.commons.cli.registry_root_for_id", lambda slug: alpha)
    monkeypatch.setattr("science_tool.commons.cli.resolve_commons_root", lambda: commons)

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "paper:Adams2025", "--from", "proj-alpha"],
    )

    assert result.exit_code == 0, result.output
    assert "Methods" in result.output
    assert "Limitations" in result.output
    assert "evidential strength" in result.output


def test_promote_refuses_when_it_would_orphan_a_local_owner(tmp_path, monkeypatch, runner) -> None:
    """fb-2026-07-16-004 (main): a bystander owning the SAME paper is told to join --from."""
    from science_tool.commons.cli import commons_group

    commons = tmp_path / "commons"
    _init_commons(commons)
    alpha = _bare_project_from_fixture(tmp_path, "proj-alpha", "proj-alpha")
    bystander = _bystander_owning(
        tmp_path, "cbioportal", "Adams2025", doi="10.1/adams", title="Adams Alpha Paper"
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: {"proj-alpha": alpha}[slug],
    )
    monkeypatch.setattr("science_tool.commons.cli.registry_root_for_id", lambda slug: alpha)
    monkeypatch.setattr("science_tool.commons.cli.resolve_commons_root", lambda: commons)
    _register_bystander(monkeypatch, "cbioportal", bystander)

    result = runner.invoke(
        commons_group,
        ["promote", "paper", "paper:Adams2025", "--from", "proj-alpha", "--apply"],
    )

    assert result.exit_code != 0, result.output
    assert "orphan" in result.output.lower()
    assert "--from" in result.output
    assert "cbioportal" in result.output
    assert not (commons / "papers" / "Adams2025.md").exists()


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
        "science_tool.commons.cli.prompt_resolve",
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
        "science_tool.commons.cli.prompt_resolve",
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
        "science_tool.commons.cli.prompt_resolve",
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
