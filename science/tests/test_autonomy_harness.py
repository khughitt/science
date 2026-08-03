from __future__ import annotations

import json
import os
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from science_model.autonomous_runs import RunDisposition

from science_tool.autonomy import harness as harness_module
from science_tool.autonomy.git import current_branch, worktree_status
from science_tool.autonomy.harness import HarnessError, run_supervised_audit
from science_tool.commons.errors import CommonsError

STARTED = datetime(2026, 8, 2, 9, 0, tzinfo=UTC)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _git_unchecked(root: Path, *args: str) -> str:
    """For subcommands whose ANSWER is a non-zero exit -- `git grep` reports "no match" as 1."""
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True
    ).stdout.strip()


def _commit_all(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(root),
         "commit", "-q", "-m", message],
        capture_output=True, check=True,
    )


def _shift_the_reported_instant(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Make the actor's report disagree with the instant the supervisor dictated.

    Design §8.2: the real `health` ECHOES `--generated-at`, so "dictate the instant" and "read
    it back out of the report" are observationally identical against an honest actor. Two rows
    turn on telling them apart -- the attested provenance and the record's clock -- and neither
    can be certified without an actor whose report says something else.

    Patches the FIXED subprocess seam rather than introducing an actor abstraction: §3.2
    declined actor selection, and a test-only seam would put that interface back through the
    suite's door.
    """
    real = harness_module._run_actor

    def _shifted(project_root: Path, *, report_path: Path, **kwargs):
        completed = real(project_root, report_path=report_path, **kwargs)
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        payload["generated_at"] = value
        report_path.write_text(json.dumps(payload), encoding="utf-8")
        return completed

    monkeypatch.setattr(harness_module, "_run_actor", _shifted)


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


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(CommonsError("commons store not found"), id="commons"),
        pytest.param(yaml.YAMLError("relations.yaml is malformed"), id="yaml"),
    ],
)
def test_an_ingestion_authority_failure_is_a_refusal_and_not_an_abort(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
):
    """The same guarantee as the test above, through the door its catch list did not close.

    `ingestion_authority` loads project sources, so it reaches the commons resolver and
    `yaml.safe_load` -- and `CommonsError` and `yaml.YAMLError` derive straight from
    `Exception`, so neither is caught by `(IngestError, OSError, ValueError)`. An absent
    commons store is an ORDINARY state (an unmounted share, a fresh clone, a different
    machine), not an exotic one, so this was reachable without any hostility.

    Asserted on the tree coming home rather than only on the refusal: escaping here skips the
    branch switch AND the settle, which is a strictly worse failure than the refusal itself --
    a verdict rendered, a record written, and an operator left on `auto/<slug>` to discover
    both by hand. The `finally` around step 9 is what makes the second half of this test pass
    independently of whether the catch list happens to name the exception.
    """
    start_branch = current_branch(supervised_project)

    def _explode(*args, **kwargs):
        raise failure

    monkeypatch.setattr(harness_module, "ingestion_authority", _explode)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.disposition is RunDisposition.CLEAN
    assert outcome.ingestion is None
    assert outcome.ingestion_refusal is not None

    assert outcome.record_written is True
    assert current_branch(supervised_project) == start_branch
    assert worktree_status(supervised_project) == ""


class _Unforeseen(Exception):
    """Deliberately NOT a `RuntimeError`: `HarnessError` is one, so `pytest.raises(RuntimeError)`
    would be satisfied by the harness's own normalization and certify nothing."""


def test_an_unforeseen_ingestion_failure_still_settles_the_tree(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """What the `finally` buys, and the only way to see it.

    The expected-refusal catch list and the `finally` address different outcomes. This induces
    an exception outside the refusal list: the outer catch must normalize it, and the `finally`
    must settle before that normalized error leaves the loop.

    The exception is REQUIRED to leave the refusal channel and become `HarnessError`, retaining
    the original as its cause. The `finally` is not a swallow: settlement happens first, then
    the public orchestration error contract is restored.
    """
    start_branch = current_branch(supervised_project)

    def _explode(*args, **kwargs):
        raise _Unforeseen("nobody foresaw this")

    monkeypatch.setattr(harness_module, "ingest_report", _explode)

    with pytest.raises(HarnessError, match="unexpected ingestion failure") as raised:
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert isinstance(raised.value.__cause__, _Unforeseen)
    assert current_branch(supervised_project) == start_branch
    assert worktree_status(supervised_project) == ""


def test_actor_output_cannot_follow_a_project_symlink(
    supervised_project: Path, tmp_path: Path
):
    """The actor writes to supervisor-owned storage before an anchored exclusive install."""
    outside = tmp_path / "outside-reports"
    outside.mkdir()
    reports = supervised_project / "doc" / "audits" / "reports"
    reports.parent.mkdir(parents=True, exist_ok=True)
    reports.symlink_to(outside, target_is_directory=True)
    _commit_all(supervised_project, "plant report redirect")

    with pytest.raises(HarnessError):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert list(outside.iterdir()) == []


def test_settlement_names_an_unaccounted_dirty_path(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """A named settlement cannot report success while leaving an unknown path dirty."""
    real_ingest = harness_module.ingest_report

    def _ingest_and_leave_residue(project_root: Path, *args, **kwargs):
        outcome = real_ingest(project_root, *args, **kwargs)
        (project_root / "unexpected.txt").write_text("residue\n", encoding="utf-8")
        return outcome

    monkeypatch.setattr(harness_module, "ingest_report", _ingest_and_leave_residue)

    with pytest.raises(HarnessError, match="unexpected.txt"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


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


def test_an_actor_that_leaves_the_branch_is_refused(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Design §4.4: the condition has to be INDUCED, not merely noticeable.

    The happy path never leaves `auto/<slug>`, so a loop with the branch check deleted still
    passes every other test in this module. Only an actor that wanders off it puts control on
    the comparison at all.
    """
    real = harness_module._run_actor

    def _wander(project_root: Path, **kwargs):
        completed = real(project_root, **kwargs)
        _git(project_root, "checkout", "-q", "-b", "elsewhere")
        return completed

    monkeypatch.setattr(harness_module, "_run_actor", _wander)

    with pytest.raises(HarnessError, match="left"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_a_quarantined_run_ingests_nothing(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """A denied run's report is not evidence of anything -- and neither is its shadow.

    The gate denies the entity write, so the disposition is `quarantined` -- and ingestion is
    conditioned on the DISPOSITION, not on whether a report happens to be readable.

    THE COMMIT IS ASSERTED ON, NOT ONLY THE VERDICT. `finish_run` re-materializes
    `knowledge/graph.trig` while HEAD is still `auto/<slug>`, over the tree the actor wrote,
    and `switch_branch` carries that modified file to the starting branch. A `_settle` that
    blanket-stages therefore publishes a graph naming `proposition:p9` on a branch whose own
    sources have never contained it -- the denied write's derived effect crossing the exact
    boundary the gate denied it at. Measured against the pre-fix implementation: the
    post-verdict commit held `knowledge/graph.trig`, and `git grep proposition:p9 HEAD`
    matched it, while `p9.md` itself was correctly absent.

    `git grep` over HEAD rather than over the graph file alone: the claim is about the
    STARTING BRANCH's committed state, and a check that names the graph would go quiet the
    day the leak arrives through some other derived file.
    """
    real = harness_module._run_actor

    def _also_write_elsewhere(project_root: Path, **kwargs):
        completed = real(project_root, **kwargs)
        (project_root / "entities" / "propositions" / "p9.md").write_text(
            "---\nid: proposition:p9\nkind: proposition\ntitle: P9\n---\n", encoding="utf-8"
        )
        return completed

    monkeypatch.setattr(harness_module, "_run_actor", _also_write_elsewhere)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.disposition is RunDisposition.QUARANTINED
    assert outcome.ingestion is None
    assert not (supervised_project / "doc" / "audits" / "cases").exists()

    slug = outcome.run_id.removeprefix("run:")
    assert outcome.post_verdict_commit is not None
    changed = _git(
        supervised_project, "show", "--format=", "--name-only", outcome.post_verdict_commit
    ).splitlines()

    # The record is published -- the run WAS attested -- and nothing derived from the denied
    # write travels with it. Ordered from the specific claim to the general one, so a
    # regression names the graph rather than only the set it belongs to.
    assert "knowledge/graph.trig" not in changed
    assert _git_unchecked(supervised_project, "grep", "-l", "proposition:p9", "HEAD") == ""
    assert changed == [f"runs/{slug}.md"]
    assert worktree_status(supervised_project) == ""


def test_the_attested_instant_is_the_commissioned_one(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """The provenance the supervisor attests is the one it DICTATED, not one it read back.

    `ingest_report` compares the report's `generated_at` against the attestation and refuses on
    any difference, so a supervisor that sourced its attestation from the report would agree
    with the actor by construction -- and the comparison would be a tautology.
    """
    _shift_the_reported_instant(monkeypatch, "2099-01-01T00:00:00.000000+00:00")

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.ingestion is None
    assert outcome.ingestion_refusal is not None


def test_the_record_ended_is_the_supervisors_clock(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Design §3.4.2: every wall instant comes from the supervisor, never from the actor.

    The shifted report is what makes this observable. Against an honest actor the report's
    instant IS the supervisor's, and it falls inside `before <= ended <= after` whichever
    source the record drew it from -- so a run over the untouched fixture certifies nothing
    here.
    """
    from science_tool.graph.autonomous_runs import load_run_records

    _shift_the_reported_instant(monkeypatch, "2099-01-01T00:00:00.000000+00:00")

    before = datetime.now(UTC)
    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")
    after = datetime.now(UTC)

    record = {r.id: r for r in load_run_records(supervised_project)}[outcome.run_id]

    assert before <= record.ended <= after


def test_an_actor_exit_two_still_completes(supervised_project: Path):
    """`science health` writes a complete report and THEN exits 2 for an invalid acceptance
    configuration (design §4.2), so exit 2 is not actor failure.

    `accepted_validation` must be a LIST holding an unusable entry. A scalar there is discarded
    by `accepted_validation_entries` before any check sees it, and the run exits 0 -- which
    would make this test green without ever producing the code it is about.
    """
    (supervised_project / "science.yaml").write_text(
        "name: harness-fixture\nknowledge_profiles:\n  local: local\n"
        "health:\n  accepted_validation:\n    - not-a-mapping\n",
        encoding="utf-8",
    )
    _commit_all(supervised_project, "bad acceptance")

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.actor_exit_code == 2
    assert outcome.disposition is RunDisposition.CLEAN


def test_settling_a_clean_tree_creates_no_commit(supervised_project: Path):
    """The status check is the only thing standing between `_settle` and an empty commit, and
    only the `record_written=True` branch reaches the commit call at all.

    Called directly, because the loop cannot produce this state: `finish_run` writes the record
    file, so every run that sets `record_written` arrives here with a dirty tree. Asserting on
    the happy path would certify a guard whose condition was never false, and the record-less
    test returns at the `record_written` branch without reaching this one.
    """
    from science_tool.autonomy.harness import _settle

    assert worktree_status(supervised_project) == ""
    head_before = _git(supervised_project, "rev-parse", "HEAD")

    assert _settle(
        supervised_project,
        record_written=True,
        disposition=RunDisposition.CLEAN,
        run_id="run:2026-08-02-health-audit-a1b2",
    ) is None
    assert _git(supervised_project, "rev-parse", "HEAD") == head_before


def test_a_settlement_failure_raises(supervised_project: Path, monkeypatch: pytest.MonkeyPatch):
    """Design §8.4: the happy path cannot distinguish raising from swallowing, because nothing
    raises. The condition has to be induced."""
    from science_tool.autonomy.git import GitError

    def _explode(*args, **kwargs):
        raise GitError("settlement blew up")

    monkeypatch.setattr(harness_module, "_settle", _explode)

    with pytest.raises(HarnessError, match="settled"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_a_raw_git_failure_is_normalized(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """Every orchestration failure raises `HarnessError`, including one from a helper that
    raises on its own -- the CLI catches nothing else, so an unnormalized `GitError` exits 1
    with a traceback where §3.4.1 promises 3."""
    from science_tool.autonomy.git import GitError

    def _explode(*args, **kwargs):
        raise GitError("cannot read HEAD")

    monkeypatch.setattr(harness_module, "current_branch", _explode)

    # `match=` because a bare `HarnessError` is satisfied by any failure at all: the run dying
    # somewhere else entirely would keep this green while the wrapper it names was gone.
    with pytest.raises(HarnessError, match="could not read the current branch"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_the_second_branch_read_is_normalized_too(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """`current_branch` is wrapped at TWO call sites, and one test cannot certify both.

    Patching it to raise unconditionally dies at the first (`harness.py`'s step 1), so removing
    the second wrapper -- the post-actor re-read -- leaves that test green. This one lets the
    first read succeed and fails only the second.
    """
    from science_tool.autonomy.git import GitError, current_branch as real_current_branch

    calls = {"n": 0}

    def _explode_on_the_second(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_current_branch(*args, **kwargs)
        raise GitError("cannot re-read HEAD")

    monkeypatch.setattr(harness_module, "current_branch", _explode_on_the_second)

    with pytest.raises(HarnessError, match="could not re-read the current branch"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_a_raw_staging_failure_is_normalized(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """`stage_all` raises `GitError` of its own, and nothing else in the loop normalizes it."""
    from science_tool.autonomy.git import GitError

    def _explode(*args, **kwargs):
        raise GitError("cannot stage the actor's output")

    monkeypatch.setattr(harness_module, "stage_all", _explode)

    with pytest.raises(HarnessError, match="the actor's output could not be captured"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_a_raw_report_directory_failure_is_normalized(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch
):
    """The anchored directory open raises `OSError`, a different type through `_step`."""

    @contextmanager
    def _explode(*args, **kwargs):
        raise OSError("cannot create the report directory")
        yield

    monkeypatch.setattr(harness_module, "open_dir_inside", _explode, raising=False)

    with pytest.raises(HarnessError, match="the report directory could not be created"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(CommonsError("commons store not found"), id="commons"),
        pytest.param(yaml.YAMLError("relations.yaml is malformed"), id="yaml"),
    ],
)
def test_a_source_layer_failure_is_normalized(
    supervised_project: Path, monkeypatch: pytest.MonkeyPatch, failure: Exception
):
    """Design §3.4.1 promises EVERY orchestration failure raises `HarnessError`.

    `CommonsError` and `yaml.YAMLError` derive straight from `Exception` -- neither is an
    `OSError` nor a `ValueError` -- and both are reachable from ordinary project state through
    the very step this induces: `start_run` -> `_capture` -> `materialize_graph` ->
    `load_project_sources`, which reads `relations.yaml` and resolves the configured commons
    store. Before the widening they escaped `_step` and the CLI exited 1 with a traceback where
    §3.4.1 promises 3.
    """
    def _explode(*args, **kwargs):
        raise failure

    monkeypatch.setattr(harness_module, "start_run", _explode)

    with pytest.raises(HarnessError, match="the run could not be opened"):
        run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")


def test_no_planted_vector_executes_through_the_supervised_loop(
    supervised_project: Path, plant_attacks
):
    """The whole loop over a hostile repository.

    `.git/config`, `.git/hooks/` and `$GIT_DIR/info/attributes` all belong to the ACTOR, so
    every git invocation the supervisor makes AFTER the actor runs is executing against a
    configuration the actor wrote. `test_no_planted_vector_executes_through_the_write_primitives`
    proves the primitives are hardened; it says nothing about whether the LOOP calls them, and a
    bare `subprocess.run(["git", ...])` anywhere in it bypasses every defence while that test
    stays green.

    The `plant_attacks` fixture is shared with that test rather than re-inlined -- its workshop
    is a sibling of the repository precisely so `start_run`'s clean-tree assertion still passes.

    THE POST-VERDICT COMMIT IS ASSERTED BEFORE THE SENTINELS. An empty sentinel directory is
    the assertion's whole content, and it is empty for a *second* reason too: a `_settle` that
    stopped committing would make no git calls at all, so nothing would fire and row 16 --
    this ledger's strongest row -- would quietly stop testing anything. Requiring the commit
    to exist is what makes the emptiness mean the vectors were disarmed rather than never
    reached.
    """
    sentinels = plant_attacks(supervised_project)

    outcome = run_supervised_audit(supervised_project, started=STARTED, short_id="a1b2")

    assert outcome.disposition is RunDisposition.CLEAN
    assert outcome.post_verdict_commit is not None
    fired = sorted(path.name for path in sentinels.iterdir())
    assert fired == [], f"a hostile git configuration executed during the run: {fired}"


def test_the_actor_runs_the_supervisors_own_toolkit(
    supervised_project: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Design §3.2: neither a package planted in the actor-controlled tree nor a `science` on
    `PATH` can stand in for the supervisor's own installation.

    TWO PLANTS, because the argv makes two independent commitments. `sys.executable -m
    science_tool` is what refuses a `science` resolved from `PATH` -- a different toolkit
    revision would be invisible, since `assert_toolkit_matches` checks the SUPERVISOR's toolkit
    and not the actor's. The `-P` / neutral-`cwd` pair is what refuses a `science_tool` package
    sitting in the project.

    That pair certifies as ONE control, and that is a measurement rather than a reading of the
    code. Mutating `_run_actor` three ways: `-P` alone with `cwd=project_root` passes; the
    neutral `cwd` alone with `-P` dropped passes; dropping BOTH fails with
    `the actor exited 1: shadowed`. `-m` puts the working directory on `sys.path` and `-P` is
    what removes it, so aiming `cwd` somewhere harmless and refusing to trust `cwd` are two
    answers to one question. Do not read a green result here as evidence for `-P` specifically.

    The `PATH` plant lives outside the project: an untracked executable beside the entities
    would make `start_run` refuse the dirty tree before the actor was ever started.
    """
    shadow = supervised_project / "science_tool"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("raise SystemExit('shadowed')\n", encoding="utf-8")
    (shadow / "__main__.py").write_text("raise SystemExit('shadowed')\n", encoding="utf-8")
    _commit_all(supervised_project, "plant")

    impostor_dir = tmp_path / "impostor-bin"
    impostor_dir.mkdir()
    impostor = impostor_dir / "science"
    impostor.write_text("#!/bin/sh\necho 'impostor toolkit' >&2\nexit 1\n", encoding="utf-8")
    impostor.chmod(0o755)
    monkeypatch.setenv("PATH", f"{impostor_dir}:{os.environ['PATH']}")

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
