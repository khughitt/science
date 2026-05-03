from __future__ import annotations

from pathlib import Path

from science_tool.data_worktree import hydrate_worktree_data


def test_hydrate_worktree_data_links_existing_source_data_dirs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    worktree = tmp_path / "worktree"
    (source / "data" / "processed" / "arxiv").mkdir(parents=True)
    (source / "data" / "processed" / "arxiv" / "datapackage.json").write_text("{}", encoding="utf-8")
    worktree.mkdir()

    actions = hydrate_worktree_data(project_root=worktree, source_root=source)

    assert [action.status for action in actions if action.relative_path == Path("data/processed")] == ["linked"]
    assert (worktree / "data" / "processed").is_symlink()
    assert (worktree / "data" / "processed" / "arxiv" / "datapackage.json").exists()


def test_hydrate_worktree_data_reports_existing_targets_without_replacing_them(tmp_path: Path) -> None:
    source = tmp_path / "source"
    worktree = tmp_path / "worktree"
    (source / "data" / "processed").mkdir(parents=True)
    (worktree / "data" / "processed").mkdir(parents=True)

    actions = hydrate_worktree_data(project_root=worktree, source_root=source)

    action = next(action for action in actions if action.relative_path == Path("data/processed"))
    assert action.status == "exists"
    assert not (worktree / "data" / "processed").is_symlink()


def test_hydrate_worktree_data_dry_run_does_not_create_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    worktree = tmp_path / "worktree"
    (source / "data" / "raw").mkdir(parents=True)
    worktree.mkdir()

    actions = hydrate_worktree_data(project_root=worktree, source_root=source, dry_run=True)

    action = next(action for action in actions if action.relative_path == Path("data/raw"))
    assert action.status == "would-link"
    assert not (worktree / "data").exists()


def test_hydrate_worktree_data_reports_missing_source_dirs(tmp_path: Path) -> None:
    source = tmp_path / "source"
    worktree = tmp_path / "worktree"
    source.mkdir()
    worktree.mkdir()

    actions = hydrate_worktree_data(project_root=worktree, source_root=source)

    assert {action.status for action in actions} == {"missing-source"}
