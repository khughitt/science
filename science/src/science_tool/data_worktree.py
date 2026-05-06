from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIRS = (Path("data/raw"), Path("data/processed"), Path("data/external"))


@dataclass(frozen=True)
class HydrationAction:
    relative_path: Path
    source: Path
    target: Path
    status: str
    details: str


def hydrate_worktree_data(
    *,
    project_root: Path,
    source_root: Path | None = None,
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
    dry_run: bool = False,
) -> list[HydrationAction]:
    """Expose ignored local data directories in a worktree via symlinks.

    This never copies or edits dataset contents. Existing target paths are left
    untouched so a worktree-specific data directory cannot be overwritten.
    """
    project_root = project_root.resolve()
    source_root = source_root.resolve() if source_root else find_data_source_root(project_root, data_dirs)
    actions: list[HydrationAction] = []

    for relative_path in data_dirs:
        source = source_root / relative_path
        target = project_root / relative_path
        if target.exists() or target.is_symlink():
            actions.append(
                HydrationAction(
                    relative_path=relative_path,
                    source=source,
                    target=target,
                    status="exists",
                    details="target already exists; left unchanged",
                )
            )
            continue
        if not source.exists():
            actions.append(
                HydrationAction(
                    relative_path=relative_path,
                    source=source,
                    target=target,
                    status="missing-source",
                    details="source path does not exist",
                )
            )
            continue
        if dry_run:
            actions.append(
                HydrationAction(
                    relative_path=relative_path,
                    source=source,
                    target=target,
                    status="would-link",
                    details="dry run; no filesystem changes made",
                )
            )
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=source.is_dir())
        actions.append(
            HydrationAction(
                relative_path=relative_path,
                source=source,
                target=target,
                status="linked",
                details="created symlink to source data path",
            )
        )

    return actions


def find_data_source_root(project_root: Path, data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS) -> Path:
    """Find another git worktree that has at least one ignored data directory."""
    project_root = project_root.resolve()
    for candidate in _git_worktree_roots(project_root):
        if candidate == project_root:
            continue
        if any((candidate / relative_path).exists() for relative_path in data_dirs):
            return candidate
    raise ValueError(
        "No source worktree with local data directories found. "
        "Pass --source-root pointing at a checkout that has data/raw, data/processed, or data/external."
    )


def _git_worktree_roots(project_root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=project_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"Could not inspect git worktrees from {project_root}") from exc

    roots: list[Path] = []
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            roots.append(Path(line.removeprefix("worktree ")).resolve())
    return roots
