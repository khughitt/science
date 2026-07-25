"""`science skills coverage` — portfolio skill-coverage scan."""

from __future__ import annotations

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
