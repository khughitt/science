"""Click CLI group for the `annotate` subcommands.

Phase 3.1 ships the `verify` subcommand. Later phases (P3.2+) will add
`audit`, `lift-tokens`, `list`, `ack`, `dismiss`, `fix`, `render`, and
`stats` to this group.
"""

from __future__ import annotations

from pathlib import Path

import click

from science_tool.annotation.verify import VerifyReport, verify_path


@click.group("annotate")
def annotate_group() -> None:
    """Annotation-system tooling (W3C Web Annotation sidecars)."""


@annotate_group.command("verify")
@click.option(
    "--root",
    "root_path",
    default=".",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Project root to walk for *.anno.trig files.",
)
@click.option(
    "--summary-only",
    is_flag=True,
    help="Print only aggregate counts, not per-issue lines.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Promote degraded/fuzzy warnings to failures (exit 1).",
)
def verify(root_path: Path, summary_only: bool, strict: bool) -> None:
    """Resolve every annotation's selector against its source; report drift."""
    report = verify_path(root_path.resolve())
    _emit_table(report, summary_only=summary_only)
    _exit_for_report(report, strict=strict)


def _emit_table(report: VerifyReport, *, summary_only: bool) -> None:
    if (
        report.broken == 0
        and report.degraded == 0
        and report.fuzzy == 0
        and report.source_missing == 0
        and report.parse_errors == 0
    ):
        click.echo(
            f"annotate verify: all clean "
            f"({report.annotations} annotations across {report.sidecars} sidecars; "
            f"0 broken, 0 degraded, 0 fuzzy)"
        )
        if report.superseded_skipped:
            click.echo(
                f"  ({report.superseded_skipped} already-superseded annotations skipped)"
            )
        return

    click.echo(
        f"annotate verify: {report.broken} broken, "
        f"{report.degraded} degraded, {report.fuzzy} fuzzy, "
        f"{report.source_missing} source-missing, "
        f"{report.parse_errors} parse-errors "
        f"({report.annotations} annotations across {report.sidecars} sidecars)"
    )
    if report.superseded_skipped:
        click.echo(
            f"  ({report.superseded_skipped} already-superseded annotations skipped)"
        )

    if summary_only:
        return

    for issue in report.issues:
        click.echo(
            f"  [{issue.kind}] {issue.sidecar.name} :: {issue.annotation_id}"
        )
        if issue.source:
            click.echo(f"      source: {issue.source}")
        if issue.exact_preview:
            click.echo(f"      exact:  {issue.exact_preview!r}")


def _exit_for_report(report: VerifyReport, *, strict: bool) -> None:
    if report.broken > 0 or report.parse_errors > 0:
        raise click.exceptions.Exit(1)
    if strict and (report.degraded > 0 or report.fuzzy > 0):
        raise click.exceptions.Exit(1)
