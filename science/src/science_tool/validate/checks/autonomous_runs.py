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

from science_model.autonomous_runs import AutonomousRunRecord, RunRecordError

from science_tool.autonomy.git import GitError, run_git
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
    """One hardened git command, decoded.

    The argv -- `--no-replace-objects`, and the config hardening that stops the
    repository's own `.git/config` from executing code during our reads -- is built by
    `autonomy.git` and nowhere else. A git that cannot be RUN becomes `_ScanFailed`, so a
    machine with no git on `PATH` gets an ERROR row instead of a `validate` traceback.
    """
    try:
        completed = run_git(root, *args)
    except GitError as exc:
        raise _ScanFailed(str(exc)) from exc
    return subprocess.CompletedProcess(
        args=completed.args,
        returncode=completed.returncode,
        stdout=completed.stdout.decode("utf-8", "replace"),
        stderr=completed.stderr.decode("utf-8", "replace"),
    )


def _commit_exists(root: Path, sha: str) -> bool:
    return _git(root, "rev-parse", "--verify", f"{sha}^{{commit}}").returncode == 0


def _record_added_in_range(root: Path, relative: str, base: str, head: str) -> str | None:
    """The commit inside `base..head` that ADDED `relative`, if any.

    THE FORGERY DISCRIMINATOR. The actor knows its own run id -- it has to, to write the
    trailers -- so it can commit `runs/<slug>.md` claiming `disposition: clean`. `finish`
    then hits the writer's never-overwrite rule, reports `unwired`, and leaves no durable
    record of its own; the forgery is all that survives, and every later `validate` reads
    it as an attestation.

    Timing separates the two. A supervisor-written record is created AFTER the range ends
    -- `head_commit` is an input to writing it -- and is committed later still, so it can
    never appear inside its own range. There are therefore NO false positives here: this
    ERROR only ever names a record the run itself committed.

    It is not complete, and the residual is worth naming. An actor cannot predict a
    future sha, so the only way it gets a plausible late `head_commit` into the record is
    to fill the range in afterwards -- which is exactly what leaves the ADDING commit
    inside the range. An actor content to name an EARLY `head_commit`, so that its record
    commit falls after the range, evades this. Catching that one needs a property this
    check deliberately does not have: re-deriving the basis, which is `finish`'s job.
    """
    completed = _git(
        root, "log", "--format=%H", "--diff-filter=A", "-1", f"{base}..{head}", "--", relative
    )
    if completed.returncode != 0:
        raise _ScanFailed(completed.stderr.strip() or f"git log failed for {relative}")
    return completed.stdout.strip() or None


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

    # `_commit_exists` and `_record_added_in_range` shell out too, so the same failure the
    # scan converts is reachable here. `validate` reports; it does not traceback.
    try:
        for record in records:
            yield from _record_results(root, record)
    except _ScanFailed as exc:
        yield _result(
            Severity.ERROR, RUNS_DIRNAME, f"could not verify the recorded commits: {exc}"
        )


def _record_results(root: Path, record: AutonomousRunRecord) -> Iterator[Result]:
    """Everything this check can say about one record without rebuilding its basis."""
    relative = f"{RUNS_DIRNAME}/{record.slug}.md"
    reachable = True
    for field_name, sha in (
        ("base_commit", record.base_commit),
        ("head_commit", record.head_commit),
    ):
        if not _commit_exists(root, sha):
            reachable = False
            yield _result(
                Severity.ERROR,
                relative,
                f"{record.id}: {field_name} {sha[:12]} is unreachable -- the recorded "
                "transition cannot be validated",
            )
    if not reachable:
        # A range with an unreachable end cannot be walked, so the forgery probe below
        # would fail rather than answer. The unreachable commit is already reported.
        return

    forging_commit = _record_added_in_range(
        root, relative, record.base_commit, record.head_commit
    )
    if forging_commit is not None:
        yield _result(
            Severity.ERROR,
            relative,
            f"{record.id}: its own run record was added by commit {forging_commit[:12]}, inside "
            f"the range {record.base_commit[:12]}..{record.head_commit[:12]} the record itself "
            "names -- the supervisor writes a record only after that range ends, so this "
            "attestation was written by the run it attests to",
        )
