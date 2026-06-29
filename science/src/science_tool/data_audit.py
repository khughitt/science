# science/src/science_tool/data_audit.py
"""Detection pass for `science data audit`.

Cross-checks each project file's (class × location × git-tracked) into violation
quadrants and renders the stable `--json` contract. Read-only — the fixer lives in
data_audit_fix.py. See docs/plans/2026-06-28-data-audit-design.md.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from science_tool.data_policy import (
    DEFAULT_DATA_POLICY,
    DataPolicy,
    FileClass,
    classify,
)
from science_tool.data_worktree import DEFAULT_DATA_DIRS


class Quadrant(StrEnum):
    STRANDED_RECORD = "stranded_record"
    LEAKED_PAYLOAD = "leaked_payload"
    FLAG = "flag"


@dataclass(frozen=True)
class Violation:
    quadrant: Quadrant
    path: str  # repo-relative posix
    file_class: FileClass
    proposed_target: str | None


def git_tracked_set(project_root: Path) -> set[str]:
    """Posix paths of all git-tracked files. Empty set if not a git repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    return {p for p in out.decode("utf-8").split("\0") if p}


def location(rel_path: Path, data_dirs: tuple[Path, ...]) -> str:
    for d in data_dirs:
        if rel_path == d or d in rel_path.parents:
            return "DATA"
    top = rel_path.parts[0] if rel_path.parts else ""
    if top == "results":
        return "RESULTS"
    if top == "entities":
        return "ENTITIES"
    return "TRACKED_OTHER"


def _data_subpath(rel_path: Path, data_dirs: tuple[Path, ...]) -> Path | None:
    """The path *relative to* the matching data dir, e.g. data/processed/exp/a → exp/a."""
    for d in data_dirs:
        if d in rel_path.parents:
            return rel_path.relative_to(d)
    return None


def _workflow_slug_from_siblings(project_root: Path, rel_path: Path) -> str | None:
    """Inspect a sibling datapackage for an explicit `workflow:` field only.

    Resolution step 1. The `name` field (`<workflow-slug>-<run>-<out>`) is NOT parsed:
    workflow slugs themselves contain hyphens, so the segment boundaries are ambiguous
    from the string alone. Without an explicit `workflow:` field we fall back to the
    first path segment (step 2 in the caller).
    """
    sib_dir = (project_root / rel_path).parent
    for name in ("datapackage.yaml", "datapackage.json"):
        dp_path = sib_dir / name
        if not dp_path.is_file():
            continue
        try:
            dp = yaml.safe_load(dp_path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(dp, dict):
            wf = dp.get("workflow")
            if isinstance(wf, str) and wf:
                return wf.removeprefix("workflow:")
    return None


def propose_results_target(
    project_root: Path, rel_path: Path, data_dirs: tuple[Path, ...]
) -> str | None:
    """results/<nearest-exp-or-workflow>/<substructure-beneath-segment>."""
    sub = _data_subpath(rel_path, data_dirs)
    if sub is None or not sub.parts:
        return None
    slug = _workflow_slug_from_siblings(project_root, rel_path) or sub.parts[0]
    beneath = Path(*sub.parts[1:]) if len(sub.parts) > 1 else Path(sub.name)
    return (Path("results") / slug / beneath).as_posix()


def _iter_project_files(project_root: Path, data_dirs: tuple[Path, ...]):
    """Yield (abs_path, rel_path) for project files.

    The real tree is walked without following symlinks; symlinked dirs whose realpath
    escapes project_root are pruned (avoids scanning arbitrary external trees / loops).
    A *DEFAULT_DATA_DIRS* entry that is itself a symlink (the data_worktree hydration
    case) is a known, bounded payload dir, so it gets a supplementary follow-links scan
    — its records must still be *reported* (the fixer FLAGs rather than moves them)."""
    seen: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [
            d for d in dirnames
            if d != ".git" and not _escapes_root(project_root, Path(dirpath) / d)
        ]
        for fn in filenames:
            abs_path = Path(dirpath) / fn
            if abs_path.is_symlink():
                continue
            rel = abs_path.relative_to(project_root)
            seen.add(rel.as_posix())
            yield abs_path, rel
    # Supplementary: symlinked known data dirs (not descended above).
    for d in data_dirs:
        entry = project_root / d
        if not (entry.is_symlink() and entry.is_dir()):
            continue
        for dirpath, _dirnames, filenames in os.walk(entry, followlinks=True):
            for fn in filenames:
                abs_path = Path(dirpath) / fn
                rel = abs_path.relative_to(project_root)
                if rel.as_posix() in seen:
                    continue
                seen.add(rel.as_posix())
                yield abs_path, rel


def audit_project(
    project_root: Path,
    policy: DataPolicy = DEFAULT_DATA_POLICY,
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> list[Violation]:
    tracked = git_tracked_set(project_root)
    violations: list[Violation] = []
    for abs_path, rel in _iter_project_files(project_root, data_dirs):
        try:
            size = abs_path.stat().st_size
        except OSError:
            continue
        cls = classify(rel, size, policy)
        loc = location(rel, data_dirs)
        is_tracked = rel.as_posix() in tracked
        v = _violation_for(project_root, rel, cls, loc, is_tracked, data_dirs)
        if v is not None:
            violations.append(v)
    violations.sort(key=lambda v: v.path)
    return violations


def _violation_for(project_root, rel, cls, loc, is_tracked, data_dirs) -> Violation | None:
    if cls is FileClass.RECORD and loc == "DATA":
        return Violation(
            Quadrant.STRANDED_RECORD, rel.as_posix(), cls,
            propose_results_target(project_root, rel, data_dirs),
        )
    if cls is FileClass.PAYLOAD and is_tracked and loc != "DATA":
        return Violation(
            Quadrant.LEAKED_PAYLOAD, rel.as_posix(), cls, "data/processed/" + rel.name,
        )
    if cls is FileClass.FLAG:
        return Violation(Quadrant.FLAG, rel.as_posix(), cls, None)
    return None


def _escapes_root(project_root: Path, candidate: Path) -> bool:
    """True if candidate is a symlink whose realpath is outside project_root."""
    if not candidate.is_symlink():
        return False
    try:
        real = candidate.resolve()
        root = project_root.resolve()
        return root != real and root not in real.parents
    except OSError:
        return True


_DATAPACKAGE_NAMES = ("datapackage.yaml", "datapackage.json")


def _planned_action(v: Violation) -> str:
    """The action the fixer *would* take, for read-only report parity with --fix."""
    if v.quadrant is Quadrant.STRANDED_RECORD:
        if Path(v.path).name in _DATAPACKAGE_NAMES:
            return "move+rewrite-resources"
        return "move"
    return "flag"  # leaked_payload, flag → never auto-acted


def render_json(violations: list[Violation], outcomes: "list | None" = None) -> str:
    """Stable contract. In read-only mode (outcomes is None) performed is always False
    and `action` reports the *planned* action, matching what --fix would attempt."""
    by_path = {o.violation.path: o for o in (outcomes or [])}
    rows = []
    for v in violations:
        o = by_path.get(v.path)
        row = {
            "quadrant": v.quadrant.value,
            "path": v.path,
            "class": v.file_class.value,
            "action": (o.action if o else _planned_action(v)),
            "target": v.proposed_target,
            "performed": bool(o.performed) if o else False,
        }
        if o is not None and o.basepath is not None:
            row["basepath"] = o.basepath
        if o is not None and o.rewritten_resources is not None:
            row["rewritten_resources"] = o.rewritten_resources
        rows.append(row)
    return json.dumps({"version": 1, "violations": rows}, indent=2) + "\n"
