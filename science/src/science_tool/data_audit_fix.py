# science/src/science_tool/data_audit_fix.py
"""Conservative fixer for `science data audit --fix`.

Only one automatic move direction: a stranded RECORD out of ignored data/ into
tracked results/. Leaked payloads and anything ambiguous → FLAG (never moved).
End state of a performed move: the target exists under results/ and is staged; the
source is gone; nothing is committed. See docs/plans/2026-06-28-data-audit-design.md.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from science_tool.data_audit import Quadrant, Violation


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


def _move_record(project_root: Path, v: Violation) -> FixOutcome:
    if v.proposed_target is None:
        return _flag(v, "no target could be proposed")
    src = project_root / v.path
    dst = project_root / v.proposed_target
    if dst.exists():
        if dst.read_bytes() == src.read_bytes():
            # Identical content already present; drop the stranded copy. If the source
            # was force-added (tracked), stage the deletion via git rm so we don't leave
            # an unstaged delete; otherwise a plain unlink suffices.
            if _is_tracked(project_root, v.path):
                _git(project_root, "rm", "-q", "-f", v.path)
            else:
                src.unlink()
            return FixOutcome(v, performed=True, action="move", reason="deduped")
        return _flag(v, f"destination exists with different content: {v.proposed_target}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if _is_tracked(project_root, v.path):
        _git(project_root, "mv", v.path, v.proposed_target)
    else:
        shutil.move(str(src), str(dst))
        _git(project_root, "add", v.proposed_target)
    return FixOutcome(v, performed=True, action="move")


def apply_fixes(project_root: Path, violations: list[Violation]) -> list[FixOutcome]:
    outcomes: list[FixOutcome] = []
    for v in violations:
        if v.quadrant is Quadrant.STRANDED_RECORD:
            outcomes.append(_move_record(project_root, v))
        else:  # LEAKED_PAYLOAD, FLAG → never auto-acted
            outcomes.append(_flag(v, "reported only; author decides"))
    return outcomes
