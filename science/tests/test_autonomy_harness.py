from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import RunDisposition

from science_tool.autonomy.git import current_branch, worktree_status
from science_tool.autonomy.harness import HarnessError, run_supervised_audit

STARTED = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_a_supervised_run_completes_and_leaves_the_tree_clean(supervised_project: Path):
    """Design §8: asserting the disposition alone would pass for a loop that stranded the
    operator on `auto/<slug>` with a dirty tree -- which is the failure §1.1 found by hand."""
    start_branch = current_branch(supervised_project)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.disposition is RunDisposition.CLEAN
    assert outcome.ingestion is not None and outcome.ingestion.records_written > 0
    assert outcome.ingestion_refusal is None
    assert outcome.record_written is True

    assert current_branch(supervised_project) == start_branch
    assert worktree_status(supervised_project) == ""

    slug = outcome.run_id.removeprefix("run:")
    report = f"doc/audits/reports/{slug}.json"
    assert _git(supervised_project, "ls-tree", "--name-only", f"auto/{slug}", report) == report
    assert _git(supervised_project, "ls-tree", "--name-only", "HEAD", report) == ""
    assert _git(supervised_project, "ls-tree", "--name-only", "HEAD", f"runs/{slug}.md")
    assert _git(supervised_project, "ls-tree", "-d", "--name-only", "HEAD", "doc/audits/cases")


def test_the_post_verdict_commit_carries_exactly_what_settling_swept_up(
    supervised_project: Path,
):
    """WHAT `_settle` committed, not merely that the tree ended clean.

    A CHARACTERIZATION TEST, and the two non-case entries below are the finding, not the
    expectation. `_settle` stages whatever the working tree holds after `finish_run`, and
    `finish_run` re-materializes `knowledge/graph.trig` without restoring, while `ingest_report`
    leaves `doc/audits/cases/.ingest.lock` behind. Both are derived/runtime state the operator
    never asked to commit, and whether they belong in the commit that attests a run is a design
    question above this module -- so this test pins the observed set rather than asserting the
    set anyone wants. Changing either behaviour turns this red on purpose: update the set
    deliberately, do not widen the predicate.

    The case files are not enumerated: how many findings the fixture project has is not what
    this test is about, and pinning the count would make it fail for the wrong reason.
    """
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
    assert outcome.post_verdict_commit is not None
    slug = outcome.run_id.removeprefix("run:")

    changed = _git(
        supervised_project, "show", "--format=", "--name-only", outcome.post_verdict_commit
    ).splitlines()
    cases = [path for path in changed if path.startswith("doc/audits/cases/") and path.endswith(".md")]

    assert cases, changed
    assert set(changed) - set(cases) == {
        f"runs/{slug}.md",
        # The attestation and its cases are the only two the design asks for. Below the line:
        "knowledge/graph.trig",  # `finish_run`'s `_capture` residue -- `start_run` restores, it does not
        "doc/audits/cases/.ingest.lock",  # `locked_store`'s lock file, never cleaned up
    }


def test_the_record_is_not_inside_its_own_range(supervised_project: Path):
    """`validate/checks/autonomous_runs.py`'s forgery discriminator: a supervisor-written
    record cannot appear inside the range it names."""
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
    slug = outcome.run_id.removeprefix("run:")

    added = _git(
        supervised_project, "log", "--format=%H", "--diff-filter=A", "-1",
        f"{_git(supervised_project, 'rev-parse', 'HEAD~1')}..{outcome.capture_commit}",
        "--", f"runs/{slug}.md",
    )

    assert added == ""


def test_the_capture_commit_carries_the_agent_authorship_and_the_run_trailer(
    supervised_project: Path,
):
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    author = _git(supervised_project, "log", "-1", "--format=%an <%ae>", outcome.capture_commit)
    trailer = _git(
        supervised_project, "log", "-1",
        "--format=%(trailers:key=Science-Run,valueonly)", outcome.capture_commit,
    ).strip()

    assert author == "health-audit <agent@science.local>"
    assert trailer == outcome.run_id


def test_the_post_verdict_commit_is_the_supervisors_and_unmarked(supervised_project: Path):
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
    assert outcome.post_verdict_commit is not None

    author = _git(
        supervised_project, "log", "-1", "--format=%an <%ae>", outcome.post_verdict_commit
    )
    trailer = _git(
        supervised_project, "log", "-1",
        "--format=%(trailers:key=Science-Run,valueonly)", outcome.post_verdict_commit,
    ).strip()

    assert author == "science-supervisor <supervisor@science.local>"
    assert trailer == ""


def test_the_autonomous_runs_check_is_silent_from_the_starting_branch(supervised_project: Path):
    """The whole point of committing the record OUTSIDE the auto branch: `_marked_commits`
    scans `--all` while `load_run_records` reads the current tree."""
    from science_tool.validate.checks.autonomous_runs import check_autonomous_runs
    from science_tool.validate.context import ValidateContext

    run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    # `ValidateContext` is a dataclass with six required fields; this check reads only
    # `project_root`. Shape lifted from `test_autonomy_validate_check.py::_ctx`.
    ctx = ValidateContext(
        project_root=supervised_project,
        doc_dir=supervised_project / "doc",
        specs_dir=supervised_project / "entities" / "specs",
        manifest={},
        strict=False,
        verbose=False,
    )
    observations = list(check_autonomous_runs(ctx))

    assert observations == []


def test_a_detached_head_is_refused_before_the_run_opens(supervised_project: Path):
    _git(supervised_project, "checkout", "-q", "--detach")

    with pytest.raises(HarnessError, match="named branch"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_an_existing_auto_branch_refuses_the_run(supervised_project: Path):
    _git(supervised_project, "branch", "auto/2026-08-02-health-audit-a1b2")

    with pytest.raises(HarnessError):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_the_actor_runs_the_supervisors_own_toolkit(supervised_project: Path):
    """Design §3.2: a package planted in the actor-controlled tree cannot shadow the real one.

    This certifies the PAIR of controls, not either one, and that is a measurement rather than
    a reading of the code. Mutating `_run_actor` three ways: `-P` alone with `cwd=project_root`
    passes; the neutral `cwd` alone with `-P` dropped passes; dropping BOTH fails with
    `the actor exited 1: shadowed`. So they are redundant by construction -- `-m` puts the
    working directory on `sys.path` and `-P` is what removes it, so aiming `cwd` somewhere
    harmless and refusing to trust `cwd` are two answers to one question. Do not read a green
    result here as evidence for `-P` specifically.
    """
    shadow = supervised_project / "science_tool"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("raise SystemExit('shadowed')\n", encoding="utf-8")
    (shadow / "__main__.py").write_text("raise SystemExit('shadowed')\n", encoding="utf-8")
    _git(supervised_project, "add", "-A")
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(supervised_project),
         "commit", "-q", "-m", "plant"],
        capture_output=True, check=True,
    )

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.actor_exit_code in (0, 2)
