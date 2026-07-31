"""The supervisor's two acts: open a run, and render the verdict on it.

Click stays out of this module. The whole verdict lives here so it can be exercised
without a CLI, and Task 6 is a thin command layer over `start_run` / `finish_run`.

`materialize_graph`, `capture_basis`, and `extract_change_set` are imported as
module-level names rather than called through their packages, so a test can drive their
failure modes -- each one is a distinct route to `unwired` and none of them is reachable
otherwise.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.audit.subjects import SubjectError, normalize_project_path
from science_model.autonomous_runs import (
    RUN_ID_PREFIX,
    AutonomousRunRecord,
    PolicyIdentity,
    RunBudget,
    RunDisposition,
    RunTier,
)
from science_model.evidence_broker import (
    REPLAY_PROTOCOL_VERSION,
    EvidenceExposure,
    EvidenceSession,
    EvidenceSessionSpec,
    InlineInput,
)

from science_tool.autonomy.baseline import (
    BaselineError,
    RunBaseline,
    read_baseline,
    write_baseline,
)
from science_tool.autonomy.control_plane import run_dir, run_slug
from science_tool.autonomy.extract import ExtractError, _git, extract_change_set
from science_tool.autonomy.marks import MarkIssue, verify_marks
from science_tool.autonomy.path_gate import Denial, GateInputError, evaluate
from science_tool.autonomy.record_writer import (
    RecordWriteError,
    generate_run_id,
    write_run_record,
)
from science_tool.autonomy.toolkit import (
    ToolkitError,
    assert_gate_is_external,
    assert_toolkit_matches,
    toolkit_revision,
)
from science_tool.graph.belief_basis import (
    BasisDelta,
    build_snapshot,
    capture_basis,
    compare_bases,
)
from science_tool.graph.belief_policy import DEFAULT_BELIEF_POLICY
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store.identity import graph_uri
from science_tool.graph.trig import load_trig_dataset_preserving_literals
from science_tool.evidence_broker.journal import (
    JournalError,
    count_requests,
    create_journal,
    open_journal,
    read_journal,
)


class RepositoryStateError(ValueError):
    """The working tree is not the commit the run's accounting names."""


class RunOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    disposition: RunDisposition
    record: AutonomousRunRecord | None
    reason: str
    deltas: tuple[BasisDelta, ...] = ()
    denials: tuple[Denial, ...] = ()
    mark_issues: tuple[MarkIssue, ...] = ()


def assert_repository_is_at(project_root: Path, expected_head: str | None = None) -> str:
    """Return HEAD, refusing any tree state this design cannot judge.

    THE BINDING BETWEEN THE TWO LAYERS. The path gate reads `base..head` out of history;
    the semantic capture reads the WORKING TREE. Nothing else forces those to describe
    the same state, and an uncommitted edit that is denied by the gate but does not move
    the basis is invisible to both -- a clean verdict over a violation still sitting on
    disk.

    Untracked files count. An untracked entity file is as absent from `base..head` and as
    present in the capture as a modified one.

    Called BEFORE `materialize_graph`, never after: materialization rewrites the tracked
    file `knowledge/graph.trig`, so checking afterwards would fail on the supervisor's own
    write.
    """
    head = _git(project_root, "rev-parse", "HEAD").decode("utf-8", "replace").strip()
    if expected_head is not None and head != expected_head:
        raise RepositoryStateError(
            f"the repository HEAD is {head}, but the run's accounting names {expected_head}. "
            "The gate would read one range while the basis was captured from another state."
        )
    status = _git(project_root, "status", "--porcelain").decode("utf-8", "replace").strip()
    if status:
        raise RepositoryStateError(
            f"{project_root} has uncommitted changes, so the working tree is not commit "
            f"{head}:\n{status}\nThe belief basis is captured from the tree while the path "
            "gate reads committed history; an uncommitted change is judged by neither."
        )
    return head


def _capture(project_root: Path):
    """Re-materialize and capture. Returns the `InstrumentResult` from `capture_basis`.

    Materialization is not optional (design §6 / Global Constraint 4): `graph.trig` is
    derived state the actor controls, so a run that edited entities and never rebuilt
    would otherwise be judged against a stale graph and pass.
    """
    trig_path = materialize_graph(project_root)
    dataset = load_trig_dataset_preserving_literals(trig_path)
    return capture_basis(
        dataset.graph(graph_uri("graph/knowledge")),
        dataset.graph(graph_uri("graph/provenance")),
    )


def start_run(
    project_root: Path,
    *,
    agent: str,
    model: str,
    tier: RunTier,
    short_id: str,
    started: datetime,
    baseline_out: Path | None = None,
    evidence: EvidenceSessionSpec | None = None,
) -> RunBaseline:
    """Open a run and return its baseline.

    Writes NO run record: `AutonomousRunRecord` has no in-flight shape, so a supervisor
    that dies mid-run leaves an unattested branch rather than a half-attested one.

    Does not create the branch or check anything out. The supervisor names the branch the
    actor is expected to work on; creating it is the harness's job (S5).

    Raises rather than returning a disposition. There is no run yet to attest to, so
    there is nothing to be `unwired` about -- the caller reports the failure and exits.
    """
    run_id = generate_run_id(started.date(), agent, short_id)
    if (baseline_out is None) == (evidence is None):
        raise BaselineError(
            "start requires exactly one of a baseline path or a broker spec; they are mutually "
            "exclusive because a brokered run's baseline is derived from the control plane"
        )
    assert_gate_is_external(project_root)
    base_commit = assert_repository_is_at(project_root)

    result = _capture(project_root)
    if result.status == "unwired":
        raise BaselineError(f"no belief basis to open a run against: ({result.code}) {result.reason}")

    session: EvidenceSession | None = None
    if evidence is not None:
        directory = run_dir(project_root, run_id)
        baseline_out = directory / "baseline.json"
        session = EvidenceSession(
            session_id=run_slug(run_id),
            journal_path=directory / "journal.jsonl",
            commit=base_commit,
            budget=evidence.budget,
            surface_policy=evidence.surface_policy,
            instrument=evidence.instrument,
            inline=_read_inline_manifest(evidence.inline_paths, project_root=project_root),
        )
        create_journal(session.journal_path, project_root=project_root, inline=session.inline)

    baseline = RunBaseline(
        run_id=run_id,
        agent=agent,
        model=model,
        tier=tier,
        branch=f"auto/{run_id.removeprefix('run:')}",
        base_commit=base_commit,
        toolkit_revision=toolkit_revision(),
        policy_identity=PolicyIdentity(
            id=DEFAULT_BELIEF_POLICY.policy_id, version=DEFAULT_BELIEF_POLICY.version
        ),
        started=started,
        snapshot=build_snapshot(result.rows),
        evidence=session,
    )
    assert baseline_out is not None
    write_baseline(baseline_out, baseline, project_root=project_root)
    return baseline


def _read_inline_manifest(
    paths: tuple[Path, ...], *, project_root: Path
) -> tuple[InlineInput, ...]:
    manifest: list[InlineInput] = []
    for path in paths:
        try:
            target = normalize_project_path(str(path))
        except SubjectError as exc:
            raise BaselineError(f"inline input {path} is not a project-relative path: {exc}") from exc
        try:
            payload = (project_root / target).read_bytes()
        except OSError as exc:
            raise BaselineError(f"could not read inline input {target}: {exc}") from exc
        manifest.append(
            InlineInput(
                target=target,
                sha256=hashlib.sha256(payload).hexdigest(),
                lines=len(payload.splitlines()),
            )
        )
    return tuple(manifest)


def finish_run(
    project_root: Path,
    *,
    baseline_path: Path,
    expect_run: str | None = None,
    head: str,
    ended: datetime,
    tokens: int | None,
    wall_clock_seconds: float | None,
    report_path: str | None = None,
) -> RunOutcome:
    """Close a run and render its verdict. Never raises for an expected condition.

    Every failure that prevents a verdict becomes `unwired`, which BLOCKS -- a guard that
    cannot see must not report clean. Two unwired shapes, and the difference is whether
    the run's identity is known:

    * The baseline is missing or untrustworthy -> `run_id`, `agent`, `branch`, and
      `base_commit` are all unknown, so no record can be written and `record` is None. An
      invented record here would be the fabrication this slice exists to prevent.
    * The baseline loaded but the verdict is uncomputable -> identity IS known, so an
      attestation saying "we could not tell" is written, with no `basis_digest`.
    """
    try:
        baseline = read_baseline(baseline_path, project_root=project_root)
    except BaselineError as exc:
        return RunOutcome(disposition=RunDisposition.UNWIRED, record=None, reason=str(exc))

    if expect_run is not None and baseline.run_id.removeprefix(
        RUN_ID_PREFIX
    ) != expect_run.removeprefix(RUN_ID_PREFIX):
        return RunOutcome(
            disposition=RunDisposition.UNWIRED,
            record=None,
            reason=f"the baseline at {baseline_path} names {baseline.run_id!r}, not {expect_run!r}",
        )

    exposure: EvidenceExposure | None = None
    if baseline.evidence is not None:
        try:
            exposure = _seal_evidence(baseline.evidence, project_root=project_root)
        except (JournalError, ValidationError) as exc:
            return RunOutcome(
                disposition=RunDisposition.UNWIRED,
                record=None,
                reason=f"the brokered run's exposure could not be sealed: {exc}",
            )

    def _unwired(reason: str) -> RunOutcome:
        return _finalize(
            project_root, baseline,
            disposition=RunDisposition.UNWIRED, reason=reason, head=head, ended=ended,
            tokens=tokens, wall_clock_seconds=wall_clock_seconds,
            evidence=exposure,
        )

    try:
        assert_gate_is_external(project_root)
        assert_toolkit_matches(baseline.toolkit_revision)
    except ToolkitError as exc:
        return _unwired(str(exc))

    try:
        assert_repository_is_at(project_root, head)
    # `ExtractError` too: `assert_repository_is_at` asks git, and `_git` fails closed on
    # any non-zero exit or OSError -- a `project_root` that is not a repository at all
    # arrives here. Global Constraint 3 makes every condition that prevents a verdict
    # `unwired`, so this must return rather than raise out of `finish_run`.
    except (RepositoryStateError, ExtractError) as exc:
        return _unwired(str(exc))

    try:
        result = _capture(project_root)
    # Deliberately broad, matching `graph belief-basis`: an unreadable graph, a failed
    # materialization, and a basis that cannot be serialized are all "we could not
    # compute the observable", and none of them is a belief movement.
    except Exception as exc:
        return _unwired(f"could not recapture the belief basis: {exc}")
    if result.status == "unwired":
        return _unwired(f"({result.code}) {result.reason}")

    deltas = tuple(compare_bases(baseline.snapshot.rows, result.rows))

    try:
        change_set = extract_change_set(project_root, baseline.base_commit, head)
        verdict = evaluate(change_set, tier=baseline.tier, report_path=report_path)
    except (ExtractError, GateInputError) as exc:
        return _unwired(f"could not evaluate the path gate: {exc}")

    try:
        mark_issues = verify_marks(
            project_root, baseline.base_commit, head, run_id=baseline.run_id, agent=baseline.agent
        )
    # `verify_marks` reads `base..head` through the same fail-closed `_git`. A range git
    # cannot read is a range whose marks are unknown, which is not the same as a range
    # whose marks are fine.
    except ExtractError as exc:
        return _unwired(f"could not verify the run's commit marks: {exc}")

    if deltas or verdict.denials or mark_issues:
        return _finalize(
            project_root, baseline,
            disposition=RunDisposition.QUARANTINED,
            reason=(
                f"{len(deltas)} belief-basis delta(s), {len(verdict.denials)} path-gate "
                f"denial(s), {len(mark_issues)} commit-mark issue(s)"
            ),
            head=head, ended=ended, tokens=tokens, wall_clock_seconds=wall_clock_seconds,
            deltas=deltas, denials=tuple(verdict.denials), mark_issues=mark_issues,
            evidence=exposure,
        )

    return _finalize(
        project_root, baseline,
        disposition=RunDisposition.CLEAN,
        reason="belief basis unmoved, every change on the tier's allowlist, marks consistent",
        head=head, ended=ended, tokens=tokens, wall_clock_seconds=wall_clock_seconds,
        evidence=exposure,
    )


def _seal_evidence(session: EvidenceSession, *, project_root: Path) -> EvidenceExposure:
    """Copy the descriptor-pinned journal into the permanent run record."""
    with open_journal(session.journal_path, project_root=project_root) as handle:
        entries = read_journal(handle)
    stamped = tuple(
        entry.model_copy(update={"commit": session.commit}) if entry.op == "inline" else entry
        for entry in entries
    )
    return EvidenceExposure(
        commit=session.commit,
        budget=session.budget,
        requests_used=count_requests(stamped),
        instrument=session.instrument,
        surface_policy=session.surface_policy,
        inline=session.inline,
        replay_protocol=REPLAY_PROTOCOL_VERSION,
        entries=stamped,
    )


def file_quarantine_feedback(outcome: RunOutcome, *, feedback_dir: Path, project: str) -> Path:
    """File one feedback item naming the run, the entity, and the delta (design §6).

    Escalation reuses the existing `science feedback` surface rather than inventing a
    second channel. The directory resolves OUTSIDE the project (`$SCIENCE_FEEDBACK_DIR`
    or the user config dir), so escalating writes nothing into the run's worktree.

    Only a QUARANTINE files an item. `unwired` is a blocked run with no finding to
    triage -- filing one would put "we could not tell" into a queue meant for things
    that went wrong.
    """
    from science_tool.feedback import FeedbackEntry, next_feedback_id, save_entry

    if outcome.disposition is not RunDisposition.QUARANTINED:
        raise ValueError(f"only a quarantined run files feedback, got {outcome.disposition.value!r}")
    assert outcome.record is not None  # a quarantine always has a record

    lines: list[str] = []
    for delta in outcome.deltas:
        lines.append(f"belief basis moved for {delta.entity_id}: {', '.join(delta.changed)} -- {delta.detail}")
    for denial in outcome.denials:
        location = denial.path if denial.field is None else f"{denial.path} field {denial.field!r}"
        lines.append(f"path gate denied {location} -- {denial.reason}")
    for issue in outcome.mark_issues:
        lines.append(f"commit {issue.commit[:12]} -- {issue.reason}")

    created = outcome.record.ended.date().isoformat()
    entry = FeedbackEntry(
        id=next_feedback_id(feedback_dir, created),
        created=created,
        project=project,
        target="command:autonomy-finish",
        # `feedback.VALID_CATEGORIES` is ("friction", "gap", "guidance", "suggestion",
        # "positive") -- `category` has no field validator, so an invented value like
        # "bug" would be accepted and then never appear in any category-filtered view.
        # "friction" is the honest fit: a run hit the envelope. "gap" would claim the
        # toolkit is missing a capability, which a quarantine does not establish.
        category="friction",
        status="open",
        summary=f"autonomous run {outcome.record.id} quarantined",
        detail="\n".join(lines),
        concern="tooling",
    )
    return save_entry(feedback_dir, entry)


def _finalize(
    project_root: Path,
    baseline: RunBaseline,
    *,
    disposition: RunDisposition,
    reason: str,
    head: str,
    ended: datetime,
    tokens: int | None,
    wall_clock_seconds: float | None,
    deltas: tuple[BasisDelta, ...] = (),
    denials: tuple[Denial, ...] = (),
    mark_issues: tuple[MarkIssue, ...] = (),
    evidence: EvidenceExposure | None = None,
) -> RunOutcome:
    """Build and write the attestation. The single place a record comes into existence.

    `basis_digest` is the BEFORE digest -- `baseline.snapshot.digest`, the basis at
    `base_commit`, per design §2. Not the after-digest: the field exists so a later
    validation can prove which starting state the run was judged against, and the
    after-state cannot establish that. It is omitted entirely when `unwired`, which the
    model enforces in both directions.
    """
    try:
        record = AutonomousRunRecord(
            id=baseline.run_id,
            agent=baseline.agent,
            model=baseline.model,
            tier=baseline.tier,
            branch=baseline.branch,
            base_commit=baseline.base_commit,
            head_commit=head,
            toolkit_revision=baseline.toolkit_revision,
            policy_identity=baseline.policy_identity,
            basis_digest=None if disposition is RunDisposition.UNWIRED else baseline.snapshot.digest,
            started=baseline.started,
            ended=ended,
            budget=RunBudget(tokens=tokens, wall_clock_seconds=wall_clock_seconds),
            disposition=disposition,
            evidence=evidence,
        )
    except ValidationError as exc:
        # The record could not even be constructed, so nothing is attested. Report it as
        # unwired WITHOUT a record rather than degrading to a weaker record: a record we
        # could not build is not a record we may approximate.
        return RunOutcome(
            disposition=RunDisposition.UNWIRED,
            record=None,
            reason=f"{reason}; the run record could not be built: {exc}",
            deltas=deltas, denials=denials, mark_issues=mark_issues,
        )

    try:
        write_run_record(project_root, record)
    except RecordWriteError as exc:
        # A verdict that cannot be recorded is not a verdict anyone can act on, and this
        # is where a second `finish` on an already-attested run lands.
        return RunOutcome(
            disposition=RunDisposition.UNWIRED,
            record=None,
            reason=f"{reason}; but the run record could not be written: {exc}",
            deltas=deltas, denials=denials, mark_issues=mark_issues,
        )

    return RunOutcome(
        disposition=disposition, record=record, reason=reason,
        deltas=deltas, denials=denials, mark_issues=mark_issues,
    )
