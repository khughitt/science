"""Design §6: expose run-record integrity as a `validate` check, so violations are
catchable by anyone, independent of the run harness.

INTEGRITY AND COVERAGE, NOT RECOMPUTATION. This check never builds a graph and never
checks a commit out: one `git log` traversal plus one `rev-parse` per recorded commit.
Re-deriving each historical run's basis would make `validate` runtime grow without
bound. The full before/after comparison lives in `science autonomy finish`, where the
pinned installation and the baseline both are.

`prereg_vehicles.py` establishes the precedent for shelling out to git from a check.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

from science_model.autonomous_runs import RunRecordError

from science_tool.graph.autonomous_runs import RUNS_DIRNAME, load_run_records
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE = "autonomous-runs"
TRAILER_KEY = "Science-Run"
_SEP = "\x1e"


class _ScanFailed(Exception):
    """git could not be asked. Never silently an empty result -- see `_marked_commits`."""


def _result(severity: Severity, relative: str | None, message: str) -> Result:
    return Result(severity, Path(relative) if relative is not None else None, None, message, RULE, None)


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # --no-replace-objects, as everywhere in the autonomy surface: replacement refs are
    # actor-writable and would let a tampered repository hide its own history.
    return subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *args],
        capture_output=True, text=True,
    )


def _commit_exists(root: Path, sha: str) -> bool:
    return _git(root, "rev-parse", "--verify", f"{sha}^{{commit}}").returncode == 0


def _marked_commits(root: Path) -> list[tuple[str, str]]:
    """(commit, trailer value) for every commit carrying a Science-Run trailer.

    `--all`, not the implicit HEAD. A quarantined run KEEPS its branch (design §6), so
    the unattested commits this check exists to find are exactly the ones sitting on a
    retained, unmerged `auto/*` branch. Scanning HEAD alone would make them invisible.

    `--grep` pushes the filter into git so only marked commits come back, but git still
    walks the graph -- this bounds the OUTPUT, not the traversal.

    Raises rather than returning `[]` on failure. This result gates the early return, so
    swallowing a git error would make the whole check report nothing on a repository it
    could not read.
    """
    completed = _git(
        root, "log", "--all", "-E", f"--grep=^{TRAILER_KEY}:",
        f"--format=%H{_SEP}%(trailers:key={TRAILER_KEY},valueonly){_SEP}",
    )
    if completed.returncode != 0:
        raise _ScanFailed(completed.stderr.strip() or "git log failed")
    marked: list[tuple[str, str]] = []
    for entry in completed.stdout.split(f"{_SEP}\n"):
        if not entry.strip():
            continue
        commit, trailers = entry.split(_SEP, 1)
        for line in trailers.splitlines():
            value = line.strip()
            if value:
                marked.append((commit, value))
    return marked


# order 207 puts this after `accepted_validation` (206), the current tail. A check most
# projects never trigger belongs at the end of the report, not ahead of the manifest.
@Check(section="autonomous runs...", order=207)
def check_autonomous_runs(ctx: ValidateContext) -> Iterator[Result]:
    """Run-record integrity and coverage. Silent in projects that never run unattended."""
    root = ctx.project_root
    runs_dir = root / RUNS_DIRNAME
    if not (root / ".git").exists():
        return

    try:
        marked = _marked_commits(root)
    except _ScanFailed as exc:
        yield _result(
            Severity.ERROR, None, f"could not scan history for {TRAILER_KEY} trailers: {exc}"
        )
        return

    # `is_symlink` before `exists`: a symlink to a missing target reports exists() False,
    # so an existence check alone would return "not an unattended project" for a runs/
    # the actor redirected -- the one case `load_run_records` refuses outright.
    if not runs_dir.exists() and not runs_dir.is_symlink() and not marked:
        # No records and no autonomous commits: this project does not run unattended.
        return

    try:
        records = load_run_records(root)
    except RunRecordError as exc:
        # Covers the internally-inconsistent record too: unwired-with-a-digest fails
        # model validation inside the loader. One bad record blinds the whole check, so
        # report and stop rather than proceeding on a partial view.
        yield _result(Severity.ERROR, RUNS_DIRNAME, f"run records could not be read: {exc}")
        return

    by_id = {record.id: record for record in records}

    for commit, run_id in marked:
        if run_id not in by_id:
            yield _result(
                Severity.ERROR,
                None,
                f"commit {commit[:12]} carries {TRAILER_KEY}: {run_id} but there is no run record "
                f"for it -- unwired: autonomous commits with no attestation",
            )

    for record in records:
        relative = f"{RUNS_DIRNAME}/{record.slug}.md"
        for field_name, sha in (("base_commit", record.base_commit), ("head_commit", record.head_commit)):
            if not _commit_exists(root, sha):
                yield _result(
                    Severity.ERROR,
                    relative,
                    f"{record.id}: {field_name} {sha[:12]} is unreachable -- the recorded "
                    "transition cannot be validated",
                )
