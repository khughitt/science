"""Pin projects at a commit and enumerate the plan-entity frame.

A probe run against an unpinned tree measures nothing reproducible, so every
stage downstream reads from a detached worktree at a recorded commit.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

_STATUS_RE = re.compile(r"^status:\s*['\"]?([\w-]+)", re.M)
_ID_RE = re.compile(r"^id:\s*['\"]?([\w:.-]+)", re.M)


class DirtyTreeError(RuntimeError):
    """The working tree has uncommitted or untracked changes."""


@dataclass(frozen=True)
class Pin:
    project: str
    root: Path
    commit: str


@dataclass(frozen=True)
class FrameRow:
    plan_id: str
    project: str
    rel_path: str
    claimed_status: str
    source_sha256: str


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def assert_clean(root: Path) -> None:
    # --porcelain reports untracked files too; they are dirt for our purposes
    # because they can change what a probe sees without appearing in history.
    out = _git(root, "status", "--porcelain")
    if out:
        raise DirtyTreeError(f"{root} is not clean:\n{out}")


def pin_project(project: str, root: Path) -> Pin:
    assert_clean(root)
    return Pin(project=project, root=root, commit=_git(root, "rev-parse", "HEAD"))


@contextmanager
def pinned_worktree(pin: Pin, base: Path) -> Iterator[Path]:
    wt = base / pin.project
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(pin.root, "worktree", "add", "--detach", "-f", str(wt), pin.commit)
    try:
        yield wt
    finally:
        _git(pin.root, "worktree", "remove", "--force", str(wt))


def _frontmatter(text: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    return None if end < 0 else text[4:end]


def enumerate_frame(pin: Pin, worktree: Path) -> list[FrameRow]:
    rows: list[FrameRow] = []
    plans_dir = worktree / "entities" / "plans"
    if not plans_dir.is_dir():
        return rows
    for path in sorted(plans_dir.glob("*.md")):
        raw = path.read_bytes()
        fm = _frontmatter(raw.decode("utf-8", errors="replace"))
        if fm is None:
            continue
        id_m = _ID_RE.search(fm)
        status_m = _STATUS_RE.search(fm)
        if id_m is None:
            continue
        rows.append(
            FrameRow(
                plan_id=id_m.group(1),
                project=pin.project,
                rel_path=str(path.relative_to(worktree)),
                claimed_status=status_m.group(1) if status_m else "",
                source_sha256=hashlib.sha256(raw).hexdigest(),
            )
        )
    return rows
