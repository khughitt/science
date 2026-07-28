"""`science autonomy` -- the supervisor-facing surface of the autonomy envelope."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from science_model.autonomous_runs import RunTier

from science_tool.output import OUTPUT_FORMATS, emit


@click.group("autonomy")
def autonomy_group() -> None:
    """Evaluate what an autonomous run was permitted to write."""


@autonomy_group.command("path-gate")
@click.option("--base", required=True, help="Commit the run started from (the recorded baseline).")
@click.option("--head", required=True, help="Commit the run ended at.")
@click.option(
    "--tier",
    type=click.Choice([tier.value for tier in RunTier]),
    default=RunTier.BELIEF_NEUTRAL.value,
    show_default=True,
    help="Tier the run was attested to (design §1).",
)
@click.option(
    "--report-path",
    default=None,
    help="Repository-relative path of the run's own report -- the only path 'report-only' may write.",
)
@click.option(
    "--project-root",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
    help="Repository root the range is read from.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit the verdict as JSON.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
def path_gate_command(
    base: str,
    head: str,
    tier: str,
    report_path: str | None,
    project_root: Path,
    as_json: bool,
    output_format: str,
) -> None:
    """Decide whether a base..head range stayed inside the tier's write surface.

    Exit codes: 0 allowed, 1 denied, 2 could not evaluate. Exit 2 is explicitly NOT
    allowed -- a gate that cannot see must not report clean (design §5).
    """
    from science_tool.autonomy.extract import ExtractError, extract_change_set
    from science_tool.autonomy.path_gate import GateInputError, evaluate

    effective_format = "json" if as_json else output_format
    try:
        change_set = extract_change_set(project_root, base, head)
        verdict = evaluate(change_set, tier=RunTier(tier), report_path=report_path)
    except (ExtractError, GateInputError) as exc:
        message = f"could not evaluate: {exc}"
        emit(
            output_format=effective_format,
            payload={"allowed": False, "denials": [], "error": message},
            render_text=lambda: click.echo(message),
        )
        sys.exit(2)

    def _render_text() -> None:
        if verdict.allowed:
            click.echo(f"allowed: {len(change_set.changes)} change(s) within tier {tier!r}")
            return
        for denial in verdict.denials:
            location = denial.path if denial.field is None else f"{denial.path} field {denial.field!r}"
            click.echo(f"denied: {location} -- {denial.reason}")

    emit(
        output_format=effective_format,
        payload=verdict.model_dump(mode="json"),
        render_text=_render_text,
    )

    sys.exit(0 if verdict.allowed else 1)


@autonomy_group.command("start")
@click.option("--agent", required=True, help="Agent ROLE (e.g. curation-sweep), not the model.")
@click.option("--model", required=True, help="Model that will execute the run.")
@click.option(
    "--tier",
    type=click.Choice([tier.value for tier in RunTier]),
    default=RunTier.BELIEF_NEUTRAL.value,
    show_default=True,
    help="Tier the supervisor attests this run to (design §1).",
)
@click.option("--short-id", required=True, help="Short disambiguator for the run id.")
@click.option(
    "--baseline-out",
    type=click.Path(path_type=Path),
    required=True,
    help="Where to write the baseline. MUST be outside the project root.",
)
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True,
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit the summary as JSON.")
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
def start_command(
    agent: str, model: str, tier: str, short_id: str, baseline_out: Path,
    project_root: Path, as_json: bool, output_format: str,
) -> None:
    """Open a run: capture the belief basis and write the supervisor's baseline.

    Writes NO run record. A supervisor that dies mid-run leaves no attestation, so its
    branch reads as unattested rather than clean.

    Exit codes: 0 opened, 2 could not open.
    """
    from datetime import UTC, datetime

    from science_model.autonomous_runs import RunRecordError

    from science_tool.autonomy.baseline import BaselineError
    from science_tool.autonomy.extract import ExtractError
    from science_tool.autonomy.lifecycle import RepositoryStateError, start_run
    from science_tool.autonomy.toolkit import ToolkitError

    effective_format = "json" if as_json else output_format
    try:
        baseline = start_run(
            project_root, agent=agent, model=model, tier=RunTier(tier), short_id=short_id,
            started=datetime.now(UTC), baseline_out=baseline_out,
        )
    # `ExtractError` too: `assert_repository_is_at` asks git through `extract._git`, which
    # fails closed on any non-zero exit -- a `--project-root` that is not a repository at
    # all arrives here, and without it `start` tracebacks instead of exiting 2.
    except (RunRecordError, ToolkitError, RepositoryStateError, BaselineError, ExtractError) as exc:
        message = f"could not start: {exc}"
        emit(
            output_format=effective_format,
            payload={"started": False, "error": message},
            render_text=lambda: click.echo(message),
        )
        sys.exit(2)

    payload = {
        "started": True,
        "run_id": baseline.run_id,
        "branch": baseline.branch,
        "base_commit": baseline.base_commit,
        "toolkit_revision": baseline.toolkit_revision,
        "basis_digest": baseline.snapshot.digest,
        "baseline_path": str(baseline_out),
    }
    emit(
        output_format=effective_format,
        payload=payload,
        render_text=lambda: click.echo(
            f"started {baseline.run_id} (base {baseline.base_commit[:12]}) -> {baseline_out}"
        ),
    )
    sys.exit(0)


@autonomy_group.command("finish")
@click.option(
    "--baseline", "baseline_path", type=click.Path(path_type=Path), required=True,
    help="Baseline written by `autonomy start`. MUST be outside the project root.",
)
@click.option("--head", required=True, help="Commit the run ended at.")
@click.option(
    "--tokens", type=int, default=None,
    help="Tokens consumed (S4 consumes this). At least one budget option is required.",
)
@click.option(
    "--wall-clock-seconds", type=float, default=None,
    help="Wall-clock seconds consumed. At least one budget option is required.",
)
@click.option(
    "--report-path", default=None,
    help="Repository-relative path of the run's own report, if it wrote one.",
)
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True,
)
@click.option("--json", "as_json", is_flag=True, default=False)
@click.option(
    "--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True,
)
def finish_command(
    baseline_path: Path, head: str, tokens: int | None, wall_clock_seconds: float | None,
    report_path: str | None, project_root: Path, as_json: bool, output_format: str,
) -> None:
    """Close a run: re-materialize, recapture the basis, gate, and attest.

    Exit codes: 0 clean, 1 quarantined, 2 unwired. Exit 2 is explicitly NOT clean --
    a guard that cannot see must not report clean (design §5).
    """
    from datetime import UTC, datetime

    from science_model.autonomous_runs import RunDisposition

    from science_tool.autonomy.lifecycle import file_quarantine_feedback, finish_run
    from science_tool.feedback_cli import resolve_feedback_dir

    # `RunBudget` requires at least one of the two, so omitting both would raise a
    # ValidationError deep inside record construction and surface as `unwired` -- an
    # attestation saying "we could not tell" written because of an operator typo. Catch
    # it here, where it is an argument error and nothing has run yet.
    if tokens is None and wall_clock_seconds is None:
        raise click.UsageError("pass --tokens, --wall-clock-seconds, or both")

    effective_format = "json" if as_json else output_format
    outcome = finish_run(
        project_root, baseline_path=baseline_path, head=head, ended=datetime.now(UTC),
        tokens=tokens, wall_clock_seconds=wall_clock_seconds, report_path=report_path,
    )

    # The record is already on disk and cannot be rewritten. Escalation failing must not
    # crash the command afterwards: a retry would hit `write_run_record`'s never-overwrite
    # rule and the run could never be finished at all. Report the failure and keep the
    # disposition's own exit code -- the quarantine is the finding, the feedback item is
    # only its delivery.
    feedback_path: Path | None = None
    feedback_error: str | None = None
    if outcome.disposition is RunDisposition.QUARANTINED:
        try:
            feedback_path = file_quarantine_feedback(
                outcome, feedback_dir=resolve_feedback_dir(), project=project_root.resolve().name
            )
        except OSError as exc:
            feedback_error = f"could not file the quarantine feedback item: {exc}"

    payload = outcome.model_dump(mode="json")
    payload["feedback_path"] = str(feedback_path) if feedback_path is not None else None
    payload["feedback_error"] = feedback_error

    def _render_text() -> None:
        click.echo(f"{outcome.disposition.value}: {outcome.reason}")
        for delta in outcome.deltas:
            click.echo(f"  basis moved: {delta.entity_id} ({', '.join(delta.changed)})")
        for denial in outcome.denials:
            location = denial.path if denial.field is None else f"{denial.path} field {denial.field!r}"
            click.echo(f"  denied: {location} -- {denial.reason}")
        for issue in outcome.mark_issues:
            click.echo(f"  mark: {issue.commit[:12]} -- {issue.reason}")
        if feedback_path is not None:
            click.echo(f"  filed {feedback_path}")
        if feedback_error is not None:
            click.echo(f"  WARNING: {feedback_error}")

    emit(output_format=effective_format, payload=payload, render_text=_render_text)
    sys.exit({RunDisposition.CLEAN: 0, RunDisposition.QUARANTINED: 1, RunDisposition.UNWIRED: 2}[outcome.disposition])
