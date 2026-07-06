# science/qa/src/science_qa/cli.py
from __future__ import annotations

from pathlib import Path

import click

from science_qa.aspects.tabular import CategoricalSpecError
from science_qa.compile import CompileError
from science_qa.config import QAConfigError
from science_qa.extensions import ProjectLocalError
from science_qa.program import ProgramError
from science_qa.runner import RunnerError, run_qa_datapackage
from science_qa.selectors import SelectorError


@click.group()
def cli() -> None:
    """science-qa command-line interface."""


@cli.command("run")
@click.option("--config", "config_path", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None)
@click.option("--datapackage", "datapackage_path", type=click.Path(path_type=Path, exists=True, dir_okay=False), default=None)
@click.option("--resource", "resource_name", type=str, default=None)
@click.option("--report-dir", "report_dir", type=click.Path(path_type=Path), default=Path("."), show_default=True)
@click.option("--no-strict", is_flag=True, default=False,
              help="Suppress the build-fatal exit code (local inspection only; never wire into a default target).")
def run_command(config_path: Path | None, datapackage_path: Path | None, resource_name: str | None,
                report_dir: Path, no_strict: bool) -> None:
    """Run a QA program over a datapackage resource; write qa_report.{md,json}.

    Input:
      --datapackage P --resource R [--config qa.yaml]

    The resource schema is compiled to the generic 'tabular' program by default;
    optional qa.yaml supplies run-knobs.

    Exit codes: 0 = ok (or structural suppressed by --no-strict); 1 = structural
    flag fired (build-fatal); 2 = bad input.
    """
    try:
        if datapackage_path is None or resource_name is None:
            raise click.UsageError("--datapackage and --resource must be supplied together")
        result = run_qa_datapackage(datapackage_path, resource_name, report_dir, runknobs_path=config_path)
    except (QAConfigError, ProgramError, SelectorError, RunnerError, CategoricalSpecError,
            ProjectLocalError, CompileError, ValueError) as exc:
        raise click.UsageError(str(exc)) from exc
    click.echo(f"{len(result.flags)} flag(s); structural_failed={result.structural_failed}; "
               f"coverage_denominator={result.coverage.executable_denominator()}")
    if result.structural_failed and not no_strict:
        raise SystemExit(1)
