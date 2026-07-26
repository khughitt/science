"""Click commands for the research-package command group."""

from __future__ import annotations

import json
from pathlib import Path

import click
from science_model.packages.validation import check_freshness, validate_package

from science_tool.output import OUTPUT_FORMATS, emit

from .build_package import build_research_package
from .init_package import init_research_package


@click.group("research-package")
def research_package_group() -> None:
    """Research package management."""


@research_package_group.command("init")
@click.option("--name", required=True, help="Package name (slug)")
@click.option("--title", required=True, help="Human-readable title")
@click.option(
    "--workflow",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Workflow directory to read config from",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(path_type=Path),
    help="Output package directory",
)
def init_cmd(name: str, title: str, workflow: Path | None, output: Path) -> None:
    """Scaffold a new research package directory."""
    pkg_dir = init_research_package(name, title, output, workflow_dir=workflow)
    click.echo(f"Scaffolded research package at {pkg_dir}")


@research_package_group.command("validate")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--check-freshness", "check_freshness_flag", is_flag=True, help="Also check input freshness")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Project root for freshness check",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
def validate_cmd(
    path: Path,
    check_freshness_flag: bool,
    project_root: Path | None,
    as_json: bool,
    output_format: str,
) -> None:
    """Validate research package(s)."""
    packages: list[Path] = []
    if (path / "datapackage.json").is_file():
        packages.append(path)
    else:
        for dp in sorted(path.rglob("datapackage.json")):
            try:
                raw = json.loads(dp.read_text(encoding="utf-8"))
                if raw.get("profile") == "science-research-package":
                    packages.append(dp.parent)
            except (json.JSONDecodeError, OSError):
                continue

    if not packages:
        click.echo("No research packages found.")
        raise SystemExit(0)

    results = []
    has_errors = False

    for pkg_dir in packages:
        result = validate_package(pkg_dir)
        if check_freshness_flag:
            root = project_root or Path.cwd()
            freshness = check_freshness(pkg_dir, root)
            result.warnings.extend(freshness.warnings)
        results.append(result)
        if not result.ok:
            has_errors = True

    def _render() -> None:
        for result in results:
            pkg_name = Path(result.package_dir).name
            if result.ok and not result.warnings:
                click.echo(f"  \u2713 {result.package_dir}")
            elif result.ok:
                for w in result.warnings:
                    click.echo(f"  \u26a0 {pkg_name}: {w}")
            else:
                for e in result.errors:
                    click.echo(f"  \u2717 {pkg_name}: {e}")

    effective_format = "json" if (as_json or output_format == "json") else output_format
    emit(
        output_format=effective_format,
        payload=[r.to_dict() for r in results],
        render_text=_render,
    )

    raise SystemExit(1 if has_errors else 0)


@research_package_group.command("build")
@click.option(
    "--results",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Results directory from workflow run",
)
@click.option(
    "--config",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Workflow config.yaml path",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(path_type=Path),
    help="Output package directory",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
    help="Output format for the build report (distinct from --output, the built package directory).",
)
@click.option(
    "--report-output",
    "report_output_path",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Write the complete, unbudgeted build report to PATH instead of stdout. Distinct from "
        "--output, which is the required built-package directory."
    ),
)
def build_cmd(
    results: Path, config: Path, output: Path, output_format: str, report_output_path: Path | None
) -> None:
    """Assemble a research package from workflow results."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

    sink = BoundedSink(
        lookup("research-package build"),
        output_path=report_output_path,
        command_path="research-package build",
        # This command's own `--output` is the required package directory, not the
        # report escape -- override the defaults so the reconstruction preserves the
        # real `--output <dir>` value and names the escape `--report-output` instead
        # of colliding with it.
        complete_via=build_complete_via(
            click.get_current_context(),
            output_hint=hint_for("research-package-build", output_format),
            escape_flag="--report-output",
            skip_params=frozenset({"report_output_path"}),
        ),
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete build report to {report_output_path}")
        if report_output_path is not None
        else None
    )

    errors = build_research_package(results, config, output)

    projected = project_rows(errors, sink.max_rows)
    displayed = projected.rows
    payload: dict[str, object] = {"package_dir": str(output), "errors": displayed}
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": sink.complete_via,
        }

    def _render() -> None:
        if displayed:
            for e in displayed:
                sink.echo(f"  \u2717 {e}")
            if projected.truncated:
                sink.echo(f"showing {len(displayed)} of {projected.total} error(s)")
                sink.echo(f"  complete output:  {sink.complete_via}")
        else:
            sink.echo(f"Built research package at {output}")

    emit(output_format=output_format, payload=payload, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)

    # Exit reflects the FULL error list, never the projected display.
    if errors:
        raise SystemExit(1)
