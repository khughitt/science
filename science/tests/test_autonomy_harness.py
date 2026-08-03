from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from science_model.autonomous_runs import RunDisposition

from science_tool.autonomy import harness as harness_module
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

    Design §4.5 names the post-verdict commit's contents exactly: `runs/<slug>.md`,
    `knowledge/graph.trig`, and any cases. The graph is REQUIRED here, not residue --
    §4.1 gives `start_run` a restore postcondition and withholds it from `finish_run` on
    purpose, because that materialization happens after the range is fixed and reflects the
    actor's work. Do not "fix" it away; removing it would break the design's named set.

    The case files are not enumerated: how many findings the fixture project has is not what
    this test is about, and pinning the count would make it fail for the wrong reason.

    `doc/audits/cases/.ingest.lock` used to show up here too: `locked_store` creates it and
    never unlinks it (by design -- see `boundary/generate.py`'s docstring), so `stage_all`
    swept it into every supervised run's commit. Task 9 closed that by teaching the
    science-managed `.gitignore` block to ignore the lock unconditionally, so it must now be
    ABSENT from the post-verdict commit.
    """
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
    assert outcome.post_verdict_commit is not None
    slug = outcome.run_id.removeprefix("run:")

    changed = _git(
        supervised_project, "show", "--format=", "--name-only", outcome.post_verdict_commit
    ).splitlines()
    cases = [path for path in changed if path.startswith("doc/audits/cases/") and path.endswith(".md")]

    assert cases, changed
    assert "doc/audits/cases/.ingest.lock" not in changed
    assert set(changed) - set(cases) == {
        # Design §4.5's named set -- nothing else.
        f"runs/{slug}.md",
        "knowledge/graph.trig",
    }


def test_a_failed_ingestion_is_a_refusal_and_not_an_abort(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """An unreadable report must not strand the operator on `auto/<slug>`.

    `load_report` reaches the filesystem, so `OSError` is a live path, and it is the one the
    loop must NOT let escape: ingestion happens between the verdict and step 9, so an
    exception here would skip the branch switch and the settle entirely -- leaving the
    operator on the run's branch with an uncommitted tree and a verdict already rendered.
    The refusal is recorded on the outcome instead, and the tree still comes home.
    """
    start_branch = current_branch(supervised_project)
    head_before = _git(supervised_project, "rev-parse", "HEAD")

    def _unreadable(*args, **kwargs):
        raise OSError("report is unreadable")

    monkeypatch.setattr(harness_module, "load_report", _unreadable)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.disposition is RunDisposition.CLEAN
    assert outcome.ingestion is None
    assert outcome.ingestion_refusal is not None
    assert "unreadable" in outcome.ingestion_refusal

    # The point of the test. A verdict was still reached and recorded, and the operator is
    # back where they started rather than parked on the run's branch.
    assert outcome.record_written is True
    assert current_branch(supervised_project) == start_branch
    assert worktree_status(supervised_project) == ""
    assert _git(supervised_project, "rev-parse", "HEAD") != head_before


def test_a_run_with_no_record_commits_nothing(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Design §4.5: no attestation means derived state must not be committed on its behalf.

    `finish_run` returns `unwired` with `record=None` on five paths. `_settle` branches on
    whether a RECORD exists rather than on the disposition, so this drives the branch through
    the shape all five produce. Without it the `restore_worktree` arm never executes at all.

    THE STUB DELEGATES TO THE REAL `finish_run` AND OVERRIDES ONLY ITS RETURN VALUE, which is
    load-bearing. A lambda that replaces it outright also removes its materialization, so the
    tree is clean when `_settle` runs and `_settle` returns at its FIRST guard -- "nothing to
    settle" -- without ever reaching the branch this test names. Verified by mutation: against
    the plain lambda, deleting the `record_written` branch outright left this test green.
    Two of the five real paths (a record that fails model validation, and one the writer
    refuses) occur inside `_finalize`, i.e. after `_capture` has already rebuilt the graph, so
    a dirty tree with no record is the state this models.
    """
    from science_tool.autonomy.lifecycle import RunOutcome, finish_run as real_finish_run

    start_branch = current_branch(supervised_project)
    head_before = _git(supervised_project, "rev-parse", "HEAD")

    def _no_record(*args, **kwargs):
        real_finish_run(*args, **kwargs)
        return RunOutcome(
            disposition=RunDisposition.UNWIRED, record=None, reason="forced"
        )

    monkeypatch.setattr(harness_module, "finish_run", _no_record)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.disposition is RunDisposition.UNWIRED
    assert outcome.record_written is False
    assert outcome.post_verdict_commit is None

    # Nothing published, and nothing left behind either: the starting branch is exactly
    # where it was, and the materialization the run produced was restored, not committed.
    assert current_branch(supervised_project) == start_branch
    assert _git(supervised_project, "rev-parse", "HEAD") == head_before
    assert worktree_status(supervised_project) == ""


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
    committer = _git(
        supervised_project, "log", "-1", "--format=%cn <%ce>", outcome.capture_commit
    )
    trailer = _git(
        supervised_project, "log", "-1",
        "--format=%(trailers:key=Science-Run,valueonly)", outcome.capture_commit,
    ).strip()

    # The split IS the design: the actor produced these bytes, the supervisor froze them.
    # Asserting only the author would leave a `commit_tree` that dropped its committer
    # overrides -- and so attributed the freezing to git's ambient identity -- uncaught.
    assert author == "health-audit <agent@science.local>"
    assert committer == "science-supervisor <supervisor@science.local>"
    assert trailer == outcome.run_id


def test_the_post_verdict_commit_is_the_supervisors_and_unmarked(supervised_project: Path):
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
    assert outcome.post_verdict_commit is not None

    author = _git(
        supervised_project, "log", "-1", "--format=%an <%ae>", outcome.post_verdict_commit
    )
    committer = _git(
        supervised_project, "log", "-1", "--format=%cn <%ce>", outcome.post_verdict_commit
    )
    trailer = _git(
        supervised_project, "log", "-1",
        "--format=%(trailers:key=Science-Run,valueonly)", outcome.post_verdict_commit,
    ).strip()

    # Both halves the supervisor's, unlike the capture commit: nothing about this commit is
    # the actor's, which is why it carries no trailer either.
    assert author == "science-supervisor <supervisor@science.local>"
    assert committer == "science-supervisor <supervisor@science.local>"
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

    # `match=` because a bare `HarnessError` is satisfied by any failure at all -- including
    # the run never reaching branch creation, which would make this test green for the
    # opposite of the reason it exists.
    with pytest.raises(HarnessError, match="an existing branch is a run-id collision"):
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


def test_the_command_exits_zero_on_a_clean_ingested_run(supervised_project: Path):
    from click.testing import CliRunner

    from science_tool.cli import main

    result = CliRunner().invoke(
        main, ["autonomy", "run", "--project-root", str(supervised_project)]
    )

    assert result.exit_code == 0, result.output


def test_the_command_exits_three_on_an_orchestration_failure(supervised_project: Path):
    from click.testing import CliRunner

    from science_tool.cli import main

    _git(supervised_project, "checkout", "-q", "--detach")

    result = CliRunner().invoke(
        main, ["autonomy", "run", "--project-root", str(supervised_project)]
    )

    assert result.exit_code == 3, result.output


def test_the_command_exits_four_when_ingestion_refuses(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Design §7: a run that produced an unusable report has not achieved its purpose, even
    though the autonomous disposition is clean."""
    from click.testing import CliRunner

    from science_tool.autonomy import harness as harness_module
    from science_tool.cli import main
    from science_tool.findings.ingest import IngestError

    def _refuse(*args, **kwargs):
        raise IngestError("refused for the test")

    monkeypatch.setattr(harness_module, "ingest_report", _refuse)

    result = CliRunner().invoke(
        main, ["autonomy", "run", "--project-root", str(supervised_project)]
    )

    assert result.exit_code == 4, result.output


@pytest.mark.parametrize(
    ("disposition", "expected_code"),
    [("quarantined", 1), ("unwired", 2)],
)
def test_the_command_maps_each_disposition_to_its_exit_code(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch, disposition, expected_code
):
    """Codes 1 and 2 need no end-to-end run: the mapping is the thing under test, and a
    constructed outcome exercises it without a second full loop."""
    from click.testing import CliRunner

    from science_tool.autonomy import harness as harness_module
    from science_tool.autonomy.harness import HarnessOutcome
    from science_tool.cli import main

    outcome = HarnessOutcome(
        run_id="run:2026-08-02-health-audit-a1b2",
        disposition=RunDisposition(disposition),
        reason="constructed for the exit-code mapping",
        actor_exit_code=0,
        capture_commit="0" * 40,
        post_verdict_commit=None,
        record_written=True,
        ingestion=None,
        ingestion_refusal=None,
    )
    # Patch the HARNESS module, not the CLI one: `run_command` imports the function inside its
    # body, so the name is resolved from `science_tool.autonomy.harness` at call time and an
    # attribute set on the CLI module would never be consulted.
    monkeypatch.setattr(harness_module, "run_supervised_audit", lambda *a, **k: outcome)

    result = CliRunner().invoke(
        main, ["autonomy", "run", "--project-root", str(supervised_project)]
    )

    assert result.exit_code == expected_code, result.output


def test_the_command_is_classified_for_the_budget_boundary():
    from science_tool.budget.registry import BUDGETS, DEFERRED, EXEMPTIONS

    assert "autonomy run" in (set(BUDGETS) | set(DEFERRED) | set(EXEMPTIONS))
