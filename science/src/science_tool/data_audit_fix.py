# science/src/science_tool/data_audit_fix.py
"""Conservative fixer for `science data audit --fix`.

Only one automatic move direction: a stranded RECORD out of ignored data/ into
tracked results/. Leaked payloads and anything ambiguous → FLAG (never moved).
End state of a performed move: the target exists under results/ and is staged; the
source is gone; nothing is committed. See docs/plans/2026-06-28-data-audit-design.md.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from science_tool.data_audit import Quadrant, Violation
from science_tool.data_worktree import DEFAULT_DATA_DIRS


@dataclass
class FixOutcome:
    violation: Violation
    performed: bool
    action: str  # "move" | "move+rewrite-resources" | "flag"
    rewritten_resources: list[dict] | None = None
    basepath: str | None = None
    reason: str | None = None


def _git(project_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(project_root), *args], check=True,
                   capture_output=True)


def _is_tracked(project_root: Path, rel: str) -> bool:
    res = subprocess.run(
        ["git", "-C", str(project_root), "ls-files", "--error-unmatch", rel],
        capture_output=True,
    )
    return res.returncode == 0


def _flag(v: Violation, reason: str) -> FixOutcome:
    return FixOutcome(v, performed=False, action="flag", reason=reason)


def _norm(*parts: str) -> str:
    return os.path.normpath(os.path.join(*parts))


def _traverses_symlinked_data_dir(
    project_root: Path, rel: str, data_dirs: tuple[Path, ...]
) -> bool:
    """True if any ancestor of rel within a data dir is a symlink, or rel's real path
    escapes project_root — i.e. moving it would mutate a shared/external source."""
    rel_path = Path(rel)
    in_data = any(d in rel_path.parents for d in data_dirs)
    if not in_data:
        return False
    cur = project_root
    for part in rel_path.parts[:-1]:
        cur = cur / part
        if cur.is_symlink():
            return True
    try:
        real = (project_root / rel_path).resolve()
        root = project_root.resolve()
        if root != real and root not in real.parents:
            return True
    except OSError:
        return True
    return False


def _rewrite_datapackage(
    project_root: Path, src_rel: str, dst_rel: str
) -> tuple[str, str | None, list[dict]] | None:
    """Return (text, basepath, rewritten) for the relocated descriptor, or None to
    signal FLAG (unresolvable / malformed). Preserves basepath AND the source
    serialization format (.json stays JSON, .yaml stays YAML); recomputes
    resources[].path against the effective resource base so resolution is invariant
    under the move."""
    is_json = src_rel.endswith(".json")
    try:
        raw = (project_root / src_rel).read_text(encoding="utf-8")
        dp = (json.loads(raw) if is_json else yaml.safe_load(raw)) or {}
    except (yaml.YAMLError, ValueError, OSError):
        return None
    if not isinstance(dp, dict):
        return None
    basepath = dp.get("basepath")
    if basepath is not None and (not isinstance(basepath, str) or os.path.isabs(basepath)):
        return None
    resources = dp.get("resources")
    if resources is not None and not isinstance(resources, list):
        return None
    src_dir = os.path.dirname(src_rel)
    dst_dir = os.path.dirname(dst_rel)
    old_base = _norm(src_dir, basepath or ".")
    new_base = _norm(dst_dir, basepath or ".")
    # A relative basepath can still resolve outside the repo (e.g. "../.." from a
    # shallow descriptor). Both effective bases must stay within project_root, else FLAG.
    if old_base.startswith("..") or new_base.startswith(".."):
        return None
    rewritten: list[dict] = []
    for res in resources or []:
        if not isinstance(res, dict):
            return None  # malformed resource entry → FLAG, never crash
        path = res.get("path")
        if not isinstance(path, str) or os.path.isabs(path):
            return None
        payload_rel = _norm(old_base, path)             # repo-relative payload
        if payload_rel.startswith(".."):                # escapes repo
            return None
        if not (project_root / payload_rel).exists():   # payload missing
            return None
        new_path = os.path.relpath(payload_rel, new_base)
        # Round-trip safety: resolution must be invariant under the move.
        if _norm(new_base, new_path) != payload_rel:
            return None
        res["path"] = new_path
        rewritten.append({"name": res.get("name"), "from": path, "to": new_path})
    text = (json.dumps(dp, indent=2) + "\n") if is_json else yaml.safe_dump(dp, sort_keys=False)
    return text, basepath, rewritten


def _move_record(
    project_root: Path, v: Violation, data_dirs: tuple[Path, ...]
) -> FixOutcome:
    if _traverses_symlinked_data_dir(project_root, v.path, data_dirs):
        return _flag(v, "source is under a symlinked data dir; move would mutate shared source")
    if v.proposed_target is None:
        return _flag(v, "no target could be proposed")
    src = project_root / v.path
    dst = project_root / v.proposed_target
    if dst.exists():
        if dst.read_bytes() == src.read_bytes():
            if _is_tracked(project_root, v.path):
                _git(project_root, "rm", "-q", "-f", v.path)
            else:
                src.unlink()
            return FixOutcome(v, performed=True, action="move", reason="deduped")
        return _flag(v, f"destination exists with different content: {v.proposed_target}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    is_dp = src.name in ("datapackage.yaml", "datapackage.json")
    if is_dp:
        rewrite = _rewrite_datapackage(project_root, v.path, v.proposed_target)
        if rewrite is None:
            return _flag(v, "datapackage resources not structurally rewritable")
        text, basepath, rewritten = rewrite
        if _is_tracked(project_root, v.path):
            _git(project_root, "rm", "-q", "--cached", v.path)
            (project_root / v.path).unlink()
        else:
            src.unlink()
        dst.write_text(text, encoding="utf-8")
        _git(project_root, "add", v.proposed_target)
        return FixOutcome(v, performed=True, action="move+rewrite-resources",
                          rewritten_resources=rewritten, basepath=basepath)
    if _is_tracked(project_root, v.path):
        _git(project_root, "mv", v.path, v.proposed_target)
    else:
        shutil.move(str(src), str(dst))
        _git(project_root, "add", v.proposed_target)
    return FixOutcome(v, performed=True, action="move")


def apply_fixes(
    project_root: Path,
    violations: list[Violation],
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> list[FixOutcome]:
    outcomes: list[FixOutcome] = []
    for v in violations:
        if v.quadrant is Quadrant.STRANDED_RECORD:
            outcomes.append(_move_record(project_root, v, data_dirs))
        else:
            outcomes.append(_flag(v, "reported only; author decides"))
    return outcomes
