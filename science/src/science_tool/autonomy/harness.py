"""The supervised run loop (Spec 2b design §4).

THE ACTOR OWNS BYTES AT ONE PATH; THE SUPERVISOR OWNS EVERYTHING ELSE -- the working tree, the
branch, both commits, the commit identities, and every attested value. Every value this module
attests is worth something only because its authority lives outside the actor, which is also
why the supervisor is deterministic code rather than a model reasoning about the work.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import yaml
from pydantic import BaseModel, ConfigDict
from science_model.autonomous_runs import RunDisposition, RunTier

from science_tool.autonomy.control_plane import run_dir
from science_tool.autonomy.git import (
    commit_tree,
    create_branch,
    current_branch,
    restore_path,
    restore_worktree,
    stage_all,
    stage_paths,
    switch_branch,
    worktree_status,
)
from science_tool.autonomy.lifecycle import finish_run, start_run
from science_tool.autonomy.marks import AGENT_EMAIL, SUPERVISOR_EMAIL, SUPERVISOR_NAME
from science_tool.autonomy.record_writer import generate_run_id
from science_tool.commons.errors import CommonsError
from science_tool.findings.ingest import (
    MAX_REPORT_BYTES,
    IngestionProvenance,
    IngestOutcome,
    ingest_report,
    ingestion_authority,
    load_report,
)
from science_tool.findings.paths import (
    create_regular_file_at,
    open_dir_inside,
    read_regular_file_bytes_at,
    unlink_at,
    write_all,
)
from science_tool.findings.storage import CASES_DIRNAME
from science_tool.graph.autonomous_runs import RUNS_DIRNAME
from science_tool.graph.health import expected_producer_ids

AGENT = "health-audit"
MODEL = "deterministic"
TIER = RunTier.REPORT_ONLY

#: The derived file `finish_run` re-materializes. Named here because `_settle` must decide
#: about it path by path -- see `_settle`.
GRAPH_PATH = "knowledge/graph.trig"


class HarnessError(RuntimeError):
    """An orchestration step failed. No outcome exists.

    Distinct from `unwired`, which is a VERDICT -- the run was judged and could not be seen.
    A `HarnessOutcome` is returned only when the loop reached a verdict, which is why
    `capture_commit` is not optional.
    """


class HarnessOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    disposition: RunDisposition
    reason: str
    actor_exit_code: int
    capture_commit: str
    post_verdict_commit: str | None
    record_written: bool
    ingestion: IngestOutcome | None
    ingestion_refusal: str | None


def generate_short_id() -> str:
    return secrets.token_hex(2)


def _now() -> datetime:
    return datetime.now(UTC)


def _run_actor(project_root: Path, *, report_path: Path, ingestion_ref: str, generated_at: str):
    """Run `science health` as a subprocess, pinned to the supervisor's own installation.

    `sys.executable` rather than a bare `science` from `PATH`: a different toolkit revision
    than the one attested in `toolkit_revision` would be invisible, since
    `assert_toolkit_matches` checks the SUPERVISOR's toolkit, not the actor's.

    `-P` keeps the current directory and the script directory off `sys.path`, and `cwd` is a
    supervisor-owned temporary directory rather than the project. The project tree is
    actor-controlled; it is the one directory this subprocess must not import from, and it is
    named only by the explicit `--project-root`.
    """
    with tempfile.TemporaryDirectory() as neutral_cwd:
        return subprocess.run(
            [
                sys.executable, "-P", "-m", "science_tool", "health",
                "--project-root", str(project_root),
                "--format", "json",
                "--output", str(report_path),
                "--ingestion-ref", ingestion_ref,
                "--generated-at", generated_at,
            ],
            cwd=neutral_cwd,
            capture_output=True,
        )


def _settle(
    project_root: Path, *, record_written: bool, disposition: RunDisposition, run_id: str
) -> str | None:
    """Leave the starting branch clean, and say whether a commit was made (design §4.5).

    Branches on whether a RECORD exists, not on the disposition: `finish_run` returns
    `unwired` with `record=None` on five paths, and a run that produced no attestation must
    not have derived state committed on its behalf.

    Checks for nothing to settle rather than passing `--allow-empty`: a `finish_run` that
    failed before `_capture` leaves no materialization behind, and an empty commit would
    record something that means nothing.

    STAGES §4.5's NAMED SET, NOT THE WHOLE TREE, AND THE GRAPH ONLY WHEN THE RUN IS CLEAN.
    `finish_run` re-materializes `knowledge/graph.trig` while HEAD is still `auto/<slug>`,
    over a tree holding whatever the actor wrote -- so on a QUARANTINED run the actor's
    source edits are left behind on that branch, as intended, while `add -A` here would
    publish their derived consequence on the starting branch: a graph naming entities the
    branch's own sources do not contain. Restoring the graph first is what keeps the record
    and the cases while dropping the denied write's shadow. `record_written` and the
    disposition are independent questions and both are asked: an `unwired`-with-identity run
    also has a record to publish and a graph nobody may trust.
    """
    if not worktree_status(project_root):
        return None
    if not record_written:
        restore_worktree(project_root)
        return None

    slug = run_id.removeprefix("run:")
    # The same spelling `record_writer.record_path` uses, from the same constant.
    staged = [f"{RUNS_DIRNAME}/{slug}.md"]
    # "and any cases" (§4.5): a run that ingested nothing has no such directory, and naming
    # an absent pathspec would make git refuse.
    if (project_root / CASES_DIRNAME).is_dir():
        staged.append(CASES_DIRNAME)
    if disposition is RunDisposition.CLEAN:
        staged.append(GRAPH_PATH)
    else:
        restore_path(project_root, GRAPH_PATH)
    stage_paths(project_root, staged)

    commit = commit_tree(
        project_root,
        message=f"chore(autonomy): record {run_id}",
        author=f"{SUPERVISOR_NAME} <{SUPERVISOR_EMAIL}>",
        committer_name=SUPERVISOR_NAME,
        committer_email=SUPERVISOR_EMAIL,
    )
    residue = worktree_status(project_root)
    if residue:
        raise HarnessError(f"settlement left unaccounted dirty paths:\n{residue}")
    return commit


@contextmanager
def _step(description: str):
    """Normalize one orchestration step's failure into `HarnessError`.

    "Every orchestration failure raises `HarnessError`" is a claim about NORMALIZATION, not
    about the functions this loop happens to call. `current_branch`, `run_dir`, `stage_all` and
    the anchored report-directory open all raise `GitError`, `PathSafetyError`, or `OSError` of
    their own, and the CLI catches only `HarnessError` -- so an unnormalized path exits 1 with a
    traceback instead of 3. Every step goes through here, and the message names the step.

    `GitError`, `BaselineError`, `RepositoryStateError` and `IngestError` are all `ValueError`
    subclasses -- verified, not assumed -- so naming those four individually would be noise
    that goes stale.

    `CommonsError` and `yaml.YAMLError` are neither, and both are reachable: `start_run` gets
    to `load_project_sources` through `_capture` -> `materialize_graph`, which raises
    `CommonsRootNotFoundError` for an absent commons store (`graph/commons_sources.py`) and
    `yaml.YAMLError` for a malformed `relations.yaml` or `science.yaml` (`graph/sources.py`).
    THE LESSON, not the list: the earlier set was verified against the autonomy and findings
    layers and never against the commons and YAML layers those two sit on, so "verified"
    covered a smaller loop than the one this function wraps. A set justified by a hierarchy
    check is only as wide as the modules the check walked.
    """
    try:
        yield
    except HarnessError:
        raise
    except (CommonsError, OSError, ValueError, yaml.YAMLError) as exc:
        raise HarnessError(f"{description}: {exc}") from exc


def run_supervised_audit(
    project_root: Path, *, started: datetime, short_id: str
) -> HarnessOutcome:
    """Open a run, run the deterministic actor, gate it, and ingest its report.

    `started` and `short_id` are parameters rather than internals so the loop is testable
    without patching a clock or a random source.
    """
    with _step("could not read the current branch"):
        starting_branch = current_branch(project_root)
    if starting_branch is None:
        raise HarnessError(
            "the harness must start from a named branch: it returns there when the run ends, "
            "and a detached HEAD gives that no destination"
        )

    # The run id must be known BEFORE `start_run`, because the baseline's location is derived
    # from it. Built with the same function `start_run` uses, not by formatting the parts by
    # hand: `generate_run_id` also validates the agent and short id, so a value the record
    # could never carry is refused here rather than after the tree has been touched.
    with _step("the run id could not be built"):
        run_id = generate_run_id(started.date(), AGENT, short_id)
        baseline_path = run_dir(project_root, run_id) / "baseline.json"

    with _step("the run could not be opened"):
        baseline = start_run(
            project_root,
            agent=AGENT, model=MODEL, tier=TIER, short_id=short_id, started=started,
            baseline_out=baseline_path,
        )

    # Not an `assert`. `AssertionError` is neither `OSError` nor `ValueError`, so it would
    # escape `_step` and exit 1 with a traceback where §3.4.1 promises 3 -- and it would
    # vanish outright under `python -O`, which is the one configuration where a baseline
    # naming another run must still stop the loop.
    if baseline.run_id != run_id:
        raise HarnessError(
            f"start_run returned a baseline for {baseline.run_id!r}, not {run_id!r}; the "
            "run this loop is about and the run its baseline attests are not the same run"
        )
    slug = run_id.removeprefix("run:")
    report_relative = f"doc/audits/reports/{slug}.json"

    with _step(
        f"could not create {baseline.branch} -- an existing branch is a run-id collision, "
        "and resuming another run's branch is not a recovery"
    ):
        create_branch(project_root, baseline.branch)

    generated_at = _now().isoformat(timespec="microseconds")
    report_path = project_root / report_relative
    report_parent, _, report_name = report_relative.rpartition("/")
    with tempfile.TemporaryDirectory() as actor_output_dir:
        actor_output_root = Path(actor_output_dir)
        actor_report = actor_output_root / report_name
        started_at = perf_counter()
        with _step("the actor could not be started"):
            completed = _run_actor(
                project_root,
                report_path=actor_report,
                ingestion_ref=run_id,
                generated_at=generated_at,
            )
        wall_clock_seconds = perf_counter() - started_at

        # Exit 2 is NOT actor failure: `science health` writes a complete report and then exits 2
        # for an invalid acceptance configuration (design §4.2).
        if completed.returncode not in (0, 2):
            raise HarnessError(
                f"the actor exited {completed.returncode}: "
                f"{completed.stderr.decode('utf-8', 'replace').strip()}"
            )

        with _step("the report directory could not be created"):
            with open_dir_inside(actor_output_root, "") as actor_dir_fd:
                payload = read_regular_file_bytes_at(
                    actor_dir_fd, report_name, MAX_REPORT_BYTES
                )
            with open_dir_inside(
                project_root, report_parent, create=True
            ) as report_dir_fd:
                descriptor = create_regular_file_at(report_dir_fd, report_name)
                try:
                    try:
                        write_all(descriptor, payload)
                    finally:
                        os.close(descriptor)
                except BaseException:
                    unlink_at(report_dir_fd, report_name)
                    raise

    with _step("could not re-read the current branch"):
        landed_on = current_branch(project_root)
    if landed_on != baseline.branch:
        raise HarnessError(
            f"the actor left {baseline.branch} for {landed_on!r}; nothing is captured, "
            "finished, or ingested, and every branch is left intact for triage"
        )

    with _step("the actor's output could not be captured"):
        stage_all(project_root)
        capture_commit = commit_tree(
            project_root,
            message=f"audit: {AGENT} report\n\nScience-Run: {run_id}",
            author=f"{AGENT} <{AGENT_EMAIL}>",
            committer_name=SUPERVISOR_NAME,
            committer_email=SUPERVISOR_EMAIL,
        )

    with _step("the run could not be finished"):
        outcome = finish_run(
            project_root,
            baseline_path=baseline_path,
            expect_run=run_id,
            head=capture_commit,
            ended=_now(),
            tokens=None,
            wall_clock_seconds=wall_clock_seconds,
            report_path=report_relative,
        )

    ingestion: IngestOutcome | None = None
    refusal: str | None = None
    # STEP 9 IS IN A `finally`, not merely after the block. Ingestion sits BETWEEN the verdict
    # and the settle, so anything escaping here strands the operator on `auto/<slug>` with an
    # uncommitted record -- the outcome the refusal set below exists to prevent, reached by a
    # door no catch list can be trusted to have closed. The list keeps the failure a REFUSAL;
    # the outer catch normalizes an unforeseen Exception; the `finally` settles before either
    # one can leave the loop.
    try:
        if outcome.disposition is RunDisposition.CLEAN:
            try:
                registry, context = ingestion_authority(project_root)
                report = load_report(project_root, report_path)
                ingestion = ingest_report(
                    project_root,
                    report,
                    registry,
                    provenance=IngestionProvenance(
                        ingestion_ref=run_id,
                        generated_at=generated_at,
                        producer_ids=frozenset(expected_producer_ids()),
                    ),
                    context=context,
                    actor=AGENT,
                )
            # THE SAME SET `findings/cli.py` CATCHES OVER THESE SAME THREE CALLS, deliberately
            # -- one refusal boundary, spelled once. `CommonsError` and `yaml.YAMLError` derive
            # straight from `Exception`, and both are reachable from ordinary project state: an
            # unmounted commons store, a malformed `relations.yaml`. `IngestError` is NOT named,
            # because it is a `ValueError` subclass and a redundant member invites the next
            # reader to widen the list by example rather than by hierarchy.
            except (CommonsError, OSError, ValueError, yaml.YAMLError) as exc:
                refusal = str(exc)
            except Exception as exc:
                raise HarnessError(f"unexpected ingestion failure: {exc}") from exc
    finally:
        with _step("the run's results could not be settled"):
            switch_branch(project_root, starting_branch)
            post_verdict_commit = _settle(
                project_root,
                record_written=outcome.record is not None,
                disposition=outcome.disposition,
                run_id=run_id,
            )

    return HarnessOutcome(
        run_id=run_id,
        disposition=outcome.disposition,
        reason=outcome.reason,
        actor_exit_code=completed.returncode,
        capture_commit=capture_commit,
        post_verdict_commit=post_verdict_commit,
        record_written=outcome.record is not None,
        ingestion=ingestion,
        ingestion_refusal=refusal,
    )
