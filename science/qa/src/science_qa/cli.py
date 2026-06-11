from __future__ import annotations

from pathlib import Path

import click

from science_qa.checks import QACheckError
from science_qa.config import QAConfigError
from science_qa.packs import UnknownPackError
from science_qa.runner import run_qa


@click.group()
def cli() -> None:
    """science-qa command-line interface."""


@cli.command("run")
@click.option("--config", "config_path", type=click.Path(path_type=Path, exists=True, dir_okay=False), required=True)
@click.option("--table", "table_path", type=click.Path(path_type=Path, exists=True, dir_okay=False), required=True)
@click.option("--report-dir", "report_dir", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--no-strict", is_flag=True, default=False,
              help="Suppress the build-fatal exit code (local inspection only; never wire into a default target).")
def run_command(config_path: Path, table_path: Path, report_dir: Path, no_strict: bool) -> None:
    """Run QA checks over a built table; write qa_report.{md,json} + reconcile dispositions.

    Exit codes: 0 = ok (or structural flags suppressed by --no-strict); 1 = structural
    flag fired (build-fatal); 2 = bad input (missing/unreadable config or table, absent
    column, unknown pack, unsupported table format).
    """
    try:
        result = run_qa(config_path, table_path, report_dir)
    except (QAConfigError, QACheckError, UnknownPackError, ValueError) as exc:
        raise click.UsageError(str(exc)) from exc
    click.echo(f"{len(result.flags)} flag(s); structural_failed={result.structural_failed}")
    if result.structural_failed and not no_strict:
        raise SystemExit(1)
