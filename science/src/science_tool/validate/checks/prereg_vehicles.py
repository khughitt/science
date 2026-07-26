"""A pre-registration must freeze its vehicle by CONTENT, not by path.

fb-2026-07-11-024 (natural-systems t830). `pre-registration:0026` locked its
vehicle as `pipeline/graph-analysis/data/graph-export.json, exported 2026-04-30,
244 models`. That path was in `.gitignore`, so the "frozen" vehicle was an
untracked build product whose content was a pure function of the working tree.
Executing the registered refresh re-ran the pipeline's first rule, regenerating
the vehicle from a catalogue that had since drifted 244 -> 248 models and
destroying the registered export irrecoverably. The 248-cohort observed
secondaries were then computed AND SEEN, making a downstream cohort decision
post-observation. Nine rounds of adversarial review did not catch it, because
nobody asked whether the named file was durable.

Freezing by path rather than by content is the flaw. Durability is mechanically
checkable, so it is checked here rather than left to review.

`data/` gets no exemption. It is gitignored by design in the standard layout,
which is precisely why it cannot by itself freeze anything: a vehicle living
there must be declared as a content-addressed dataset entity instead.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

# The obligation attaches once the document is frozen, not while it is drafted.
_FROZEN_STATUSES = frozenset({"committed", "amended"})

# Data-gated mode commits the decision rule before any vehicle is admissible,
# so it legitimately names none. The template section is the declaration.
_DATA_GATED_MARKER = "## Vehicle-Admissibility Gate"


def _frozen_because(frontmatter: dict[str, Any]) -> str | None:
    """Why this pre-registration counts as frozen, or None if it does not.

    `status` is the primary signal, but it is not the only sound one, and on
    its own it under-reports. `default_status` for this kind is `active`
    (profiles/core.py) while `templates/pre-registration.md` displays
    `status: "committed"`, so a tool-created pre-registration lands on `active`
    and stays there unless the author edits it at sign-off. natural-systems had
    7 of 34 in exactly that state, two of them with amendment records and a
    drawn null (fb-2026-07-26-019).

    A non-empty `amendments:` list is therefore read as frozen too. That is a
    sufficient condition, not a heuristic: amending presupposes having
    committed, so there is no state in which an unfrozen document legitimately
    carries one. `commands/pre-register.md` prescribes the field for exactly
    this purpose. A `committed:` DATE is deliberately NOT read -- the template
    emits it unconditionally, so it is present on every pre-registration in
    practice (34 of 34 in the surveyed project) and discriminates nothing.
    """
    if str(frontmatter.get("status", "")) in _FROZEN_STATUSES:
        return f"status is {frontmatter.get('status')!r}"
    amendments = frontmatter.get("amendments")
    if isinstance(amendments, list) and amendments:
        plural = "s" if len(amendments) != 1 else ""
        return f"it records {len(amendments)} amendment{plural}, which presupposes a commitment"
    return None


def _result(severity: Severity, relative: str, message: str, rule: str) -> Result:
    return Result(severity, Path(relative), None, message, rule, None)


def _git_ok(root: Path, *args: str) -> bool:
    """True when git exits 0. Used for the two boolean queries below."""
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True)
    return completed.returncode == 0


def _is_ignored(root: Path, relative: str) -> bool:
    return _git_ok(root, "check-ignore", "-q", "--", relative)


def _is_tracked(root: Path, relative: str) -> bool:
    return _git_ok(root, "ls-files", "--error-unmatch", "--", relative)


def _vehicle_entries(frontmatter: dict[str, Any]) -> list[Any]:
    declared = frontmatter.get("vehicles")
    if declared is None:
        return []
    if not isinstance(declared, list):
        return [declared]
    return declared


@Check(section="discussion documents...", order=13)
def check_prereg_vehicles(ctx: ValidateContext) -> Iterator[Result]:
    entities_root = ctx.project_root / resolve_path_policy("pre-registration").root
    if not entities_root.is_dir():
        return
    is_repo = (ctx.project_root / ".git").exists()

    for path in sorted(entities_root.glob("*.md")):
        if not path.is_file():
            continue
        frontmatter = ctx.frontmatter(path)
        if str(frontmatter.get("kind", "")) != "pre-registration":
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        entries = _vehicle_entries(frontmatter)

        if not entries:
            frozen_because = _frozen_because(frontmatter)
            if frozen_because is not None and _DATA_GATED_MARKER not in ctx.body(path):
                yield _result(
                    Severity.WARN,
                    relative,
                    f"{relative} is frozen ({frozen_because}) but declares no 'vehicles:'. A "
                    f"pre-registration that names its data only in prose is frozen by path, not by "
                    f"content: declare each vehicle as 'path' + 'sha256', or state the "
                    f"'{_DATA_GATED_MARKER} (data-gated mode)' section if no vehicle is admissible yet.",
                    "prereg.vehicle-undeclared",
                )
            continue

        if not is_repo:
            yield _result(
                Severity.WARN,
                relative,
                f"{relative} declares vehicles but {ctx.project_root} is not a git repository, so "
                f"their durability cannot be verified.",
                "prereg.vehicle-unverifiable",
            )
            continue

        for entry in entries:
            yield from _check_vehicle(ctx, relative, entry)


def _check_vehicle(ctx: ValidateContext, relative: str, entry: Any) -> Iterator[Result]:
    """Report the FIRST way this vehicle fails to be frozen, if any.

    The conditions are ordered by how fundamental they are: an unresolvable or
    non-durable path makes its recorded hash moot, so reporting the hash as well
    would be noise.
    """
    if not isinstance(entry, dict) or not entry.get("path"):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} has a 'vehicles:' entry with no 'path': {entry!r}.",
            "prereg.vehicle-uncontent-addressed",
        )
        return

    declared_path = str(entry["path"])
    digest = entry.get("sha256")
    if not digest:
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r} by path alone. Record its 'sha256:' — a "
            f"path names where the data was, not which data it was.",
            "prereg.vehicle-uncontent-addressed",
        )
        return

    target = ctx.project_root / declared_path
    if not target.is_file():
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r}, which does not exist.",
            "prereg.vehicle-missing",
        )
        return

    if _is_ignored(ctx.project_root, declared_path):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r}, which is gitignored. An ignored file is "
            f"a local build product, not a frozen record: regenerating it destroys the registered "
            f"content irrecoverably. Commit it, or declare it as a content-addressed dataset entity.",
            "prereg.vehicle-gitignored",
        )
        return

    if not _is_tracked(ctx.project_root, declared_path):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r}, which is not tracked by git. An "
            f"uncommitted file cannot be recovered once overwritten.",
            "prereg.vehicle-untracked",
        )
        return

    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != str(digest):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r} at sha256 {str(digest)[:12]}…, but the "
            f"file on disk is {actual[:12]}…. The registered content is gone even though the path "
            f"still resolves.",
            "prereg.vehicle-hash-drift",
        )
