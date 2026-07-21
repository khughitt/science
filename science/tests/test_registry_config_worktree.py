"""Registration must not pollute config.yaml with linked-worktree entries.

A git worktree (`.worktrees/<name>/`) is a transient, branch-specific checkout of
an already-registered project. Registering the worktree's own path adds a duplicate
`projects[]` entry that shares the project's `science.yaml` id, which later makes
`registry_root_for_id` raise "ambiguous" and breaks `commons promote`/overlay
(fb-2026-07-16-006). A build run from a worktree must register the *main checkout*.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from science_tool.graph.build import build_project_graph
from science_tool.registry.config import load_global_config, resolve_registration_root


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git_project(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text("name: proj\nid: proj\nrole: standalone\n", encoding="utf-8")
    _git(["init"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-m", "init"], root)


def test_resolve_registration_root_redirects_linked_worktree(tmp_path: Path) -> None:
    main = tmp_path / "proj"
    _init_git_project(main)
    worktree = main / ".worktrees" / "foo"
    _git(["worktree", "add", "-b", "foo", str(worktree)], main)

    assert resolve_registration_root(worktree) == main.resolve()


def test_resolve_registration_root_passthrough_for_main_checkout(tmp_path: Path) -> None:
    main = tmp_path / "proj"
    _init_git_project(main)

    assert resolve_registration_root(main) == main.resolve()


def test_resolve_registration_root_passthrough_for_non_git_dir(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    assert resolve_registration_root(plain) == plain.resolve()


def test_build_in_worktree_registers_main_checkout_not_worktree(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "isolated-config"
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(config_dir))

    main = tmp_path / "proj"
    _init_git_project(main)
    worktree = main / ".worktrees" / "foo"
    _git(["worktree", "add", "-b", "foo", str(worktree)], main)

    build_project_graph(worktree)

    cfg = load_global_config(config_dir / "config.yaml")
    assert len(cfg.projects) == 1, [p.path for p in cfg.projects]
    assert cfg.projects[0].path == str(main.resolve())
