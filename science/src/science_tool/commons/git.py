"""Git transaction primitives for commons promotion.

`_git` is the single subprocess entry point; everything else here is a repo guard
(is the tree clean? is the repo idle?) or a rollback step that returns the working
tree to HEAD after a failed promotion.

This module is a leaf: it imports the promote vocabulary, never the promote pipeline.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from science_tool.commons.promote_types import OverlayRewrite, PromoteKindConfig


def _commons_is_clean(commons_root: Path, kind: PromoteKindConfig) -> tuple[bool, list[str]]:
    """Path-limited cleanliness check. Untracked files under
    kind.commons_subdir/ or .migrations/ count as dirty."""
    status = _git(commons_root, "status", "--porcelain", "--untracked-files=all").stdout
    dirty: list[str] = []
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        flags = line[:2]
        if flags == "??":
            if path.startswith(f"{kind.commons_subdir}/") or path.startswith(".migrations/"):
                dirty.append(path)
        else:
            dirty.append(path)
    return (not dirty, dirty)


def _project_target_files_clean(
    project_root: Path,
    target_filenames: list[str],
    kind: PromoteKindConfig,
) -> tuple[bool, list[str]]:
    """For each filename in `target_filenames`, check whether the overlay
    destination AND every source subdir's same-named file are clean against
    HEAD. The multi-path scan covers cases where the source and overlay
    destination are distinct, so the preflight catches dirtiness in both."""
    dirty: list[str] = []
    subdirs_to_check = [kind.overlay_dest_subdir, *kind.source_subdirs]
    seen: set[str] = set()
    ordered: list[str] = []
    for subdir in subdirs_to_check:
        if subdir in seen:
            continue
        seen.add(subdir)
        ordered.append(subdir)

    for name in target_filenames:
        for sub in ordered:
            rel = f"{sub}/{name}"
            status = subprocess.run(
                [
                    "git",
                    "-C",
                    str(project_root),
                    "status",
                    "--porcelain",
                    "--untracked-files=all",
                    "--",
                    rel,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            if status.stdout.strip():
                dirty.append(rel)
    return (not dirty, dirty)


def _project_root_from_overlay_path(path: Path, kind: PromoteKindConfig) -> Path:
    """Derive project root from `<root>/<kind.overlay_dest_subdir>/<file>`."""
    parents_to_strip = len(Path(kind.overlay_dest_subdir).parts) + 1
    return path.parents[parents_to_strip - 1]


def _paths_for_overlay_rollback(rewrite: OverlayRewrite) -> list[Path]:
    paths = [rewrite.path]
    if rewrite.rename_from is not None:
        paths.append(rewrite.rename_from)
    if rewrite.unlinked_source is not None:
        paths.append(rewrite.unlinked_source)
    return list(dict.fromkeys(paths))


def _restore_project_rewrites_to_head(
    rewrites: list[OverlayRewrite],
    kind: PromoteKindConfig,
) -> None:
    """Restore rewritten/unlinked project paths to their pre-apply HEAD state."""
    paths_by_project: dict[Path, list[Path]] = {}
    for rewrite in rewrites:
        project_root = _project_root_from_overlay_path(rewrite.path, kind)
        for path in _paths_for_overlay_rollback(rewrite):
            paths_by_project.setdefault(project_root, []).append(path)

    for project_root, paths in paths_by_project.items():
        for path in dict.fromkeys(paths):
            rel = path.relative_to(project_root)
            existed = (
                subprocess.run(
                    ["git", "-C", str(project_root), "cat-file", "-e", f"HEAD:{rel}"],
                    capture_output=True,
                ).returncode
                == 0
            )
            if existed:
                subprocess.run(
                    ["git", "-C", str(project_root), "checkout", "HEAD", "--", str(rel)],
                    check=True,
                    capture_output=True,
                )
            else:
                path.unlink(missing_ok=True)


def _repo_is_idle(root: Path) -> bool:
    """True if the repo is NOT mid-merge/rebase/cherry-pick/bisect."""
    try:
        git_dir_result = _git(root, "rev-parse", "--git-dir", check=False)
    except OSError:
        return False
    if git_dir_result.returncode != 0:
        return False
    git_dir_raw = git_dir_result.stdout.strip()
    if not git_dir_raw:
        return False
    git_dir = Path(git_dir_raw)
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    sentinels = [
        "MERGE_HEAD",
        "REBASE_HEAD",
        "CHERRY_PICK_HEAD",
        "BISECT_LOG",
        "rebase-apply",
        "rebase-merge",
    ]
    return not any((git_dir / s).exists() for s in sentinels)


def _restore_paths_to_head(commons_root: Path, paths: list[Path]) -> None:
    """For each path, checkout HEAD -- <rel> if it existed at HEAD, else unlink.
    Used in the 'before step 5' failure path."""
    for path in paths:
        rel = path.relative_to(commons_root)
        existed = _git(commons_root, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode == 0
        if existed:
            _git(commons_root, "checkout", "HEAD", "--", str(rel))
        else:
            _git(commons_root, "rm", "--cached", "--ignore-unmatch", "--", str(rel), check=False)
            path.unlink(missing_ok=True)


def _restore_side_channel_backups(op_id: str) -> None:
    from science_tool.commons.config import restore_data_override_from_backup

    restore_data_override_from_backup(op_id=op_id)


def _git(commons_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run `git -C <commons_root> <args>` and return the CompletedProcess.

    Wrapping makes path-limited call sites readable and centralizes the cwd
    plumbing so individual helpers don't repeat `["git", "-C", str(root), ...]`.
    """
    return subprocess.run(
        ["git", "-C", str(commons_root), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def _rollback_step5(
    commons_root: Path,
    tags_attempted: list[str],
    canonical_paths: list[Path],
) -> None:
    """Non-destructive path-limited rollback for a step-5 mid-failure.

    1. Delete every tag in `tags_attempted` (idempotent — tags that never
       existed silently no-op).
    2. `git reset --soft HEAD~1` — moves HEAD back without disturbing index/wt.
    3. For each canonical_path: if it exists at the new HEAD, `git checkout
       HEAD -- <path>`. If it does NOT exist at HEAD (first-promote), unlink
       the working-tree file.

    Caller must have verified that HEAD~1 is the pre-step-4 state (the immediate
    parent of the just-undone promote commit). NEVER calls `reset --hard`.
    """
    for tag in tags_attempted:
        _git(commons_root, "tag", "-d", tag, check=False)

    # Invariant: a promote commit exists at HEAD (≥1 mint decision was committed,
    # or a dataset side-channel failure occurred after the commit), so this reset
    # never runs without a promote commit to undo.
    _git(commons_root, "reset", "--soft", "HEAD~1")

    for canonical_path in canonical_paths:
        rel = canonical_path.relative_to(commons_root)
        exists_at_head = _git(commons_root, "cat-file", "-e", f"HEAD:{rel}", check=False).returncode == 0
        if exists_at_head:
            _git(commons_root, "checkout", "HEAD", "--", str(rel))
        else:
            _git(commons_root, "rm", "--cached", "--ignore-unmatch", "--", str(rel), check=False)
            canonical_path.unlink(missing_ok=True)
