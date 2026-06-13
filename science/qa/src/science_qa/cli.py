# science/qa/src/science_qa/cli.py
from __future__ import annotations

from pathlib import Path

import click

from science_qa.aspects.tabular import CategoricalSpecError
from science_qa.config import QAConfigError
from science_qa.extensions import ProjectLocalError
from science_qa.program import ProgramError
from science_qa.runner import RunnerError, run_qa
from science_qa.selectors import SelectorError


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
    """Run a QA program over a built table; write qa_report.{md,json} + reconcile dispositions.

    Exit codes: 0 = ok (or structural suppressed by --no-strict); 1 = structural flag fired
    (build-fatal); 2 = bad input (config/table/program/selector error, unsupported format).
    """
    try:
        result = run_qa(config_path, table_path, report_dir)
    except (QAConfigError, ProgramError, SelectorError, RunnerError, CategoricalSpecError,
            ProjectLocalError, ValueError) as exc:
        raise click.UsageError(str(exc)) from exc
    click.echo(f"{len(result.flags)} flag(s); structural_failed={result.structural_failed}; "
               f"coverage_denominator={result.coverage.executable_denominator()}")
    if result.structural_failed and not no_strict:
        raise SystemExit(1)
