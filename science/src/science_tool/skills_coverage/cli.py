"""`science skills coverage` — portfolio skill-coverage scan."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from science_model.skill_coverage.coverage import (
    SkillCoverageError,
    serialize_coverage_report,
)

from science_tool.skills_coverage.scan import (
    SkillCoverageScanError,
    scan_portfolio,
    write_report_atomically,
)
from science_tool.feedback import load_all_entries
from science_tool.feedback_cli import resolve_feedback_dir
from science_tool.skills_coverage.curate import (
    CurateConflictError,
    CurateSelectionError,
    CurateStatusError,
    apply_plan,
    build_curate_plan,
    coverage_context,
    serialize_curate_plan,
)


@click.command(name="coverage")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the coverage-report JSON to PATH (atomically). Default: stdout.",
)
@click.option(
    "--project",
    "project",
    default=None,
    help="Restrict the scan to the one registered project with this identifier.",
)
def coverage_command(output: Path | None, project: str | None) -> None:
    """Scan the registered portfolio for skill-coverage gaps."""
    try:
        report = scan_portfolio(only=project)
    except (SkillCoverageScanError, SkillCoverageError) as exc:
        raise click.ClickException(str(exc)) from exc
    text = serialize_coverage_report(report)
    if output is not None:
        write_report_atomically(output, text)
    else:
        click.echo(text, nl=False)


@click.command(name="curate")
@click.option("--apply", "apply_", is_flag=True, help="File feedback for the plan (default: report only, no writes).")
@click.option("--term", "terms", multiple=True, help="With --apply, file only these term(s). Repeatable.")
@click.option("--project", "project", default=None, help="Restrict the scan to one registered project.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Write the complete report to PATH (atomically) instead of stdout. "
                   "Report-only: cannot be combined with --apply.")
def curate_command(apply_: bool, terms: tuple[str, ...], project: str | None, fmt: str, output: Path | None) -> None:
    """Triage uncovered skill-coverage gaps into `science feedback` (report-first)."""
    if terms and not apply_:
        raise click.ClickException("--term requires --apply")
    # --output is report-only. Combined with --apply, a failing report-write would
    # follow a committed feedback write (a retry would then double-record), so reject
    # the combination outright. Apply results already print to stdout (redirect for audit).
    if apply_ and output is not None:
        raise click.ClickException("--output cannot be combined with --apply (results go to stdout)")
    try:
        report = scan_portfolio(only=project)
    except (SkillCoverageScanError, SkillCoverageError) as exc:
        raise click.ClickException(str(exc)) from exc

    feedback_dir = resolve_feedback_dir()
    entries = load_all_entries(feedback_dir)
    try:
        plan = build_curate_plan(report.candidates, entries, coverage_context(report), report.scope.to_dict())
    except (CurateConflictError, CurateStatusError) as exc:
        raise click.ClickException(str(exc)) from exc

    if apply_:
        try:
            plan = apply_plan(plan, feedback_dir, today=date.today().isoformat(),
                              selected_terms=set(terms) or None)
        except CurateSelectionError as exc:
            raise click.ClickException(str(exc)) from exc

    text = serialize_curate_plan(plan, fmt)
    if output is not None:
        write_report_atomically(output, text)
    else:
        click.echo(text, nl=False)
