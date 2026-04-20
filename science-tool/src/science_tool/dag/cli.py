"""Click CLI group for the ``dag`` subcommands."""

from __future__ import annotations

import json
import sys as _sys
from pathlib import Path

import click

from science_tool.dag.audit import run_audit
from science_tool.dag.init import init_dag
from science_tool.dag.number import number_all, number_one
from science_tool.dag.paths import DagPaths, load_dag_paths
from science_tool.dag.render import render_all, render_one
from science_tool.dag.schema import EdgesYamlFile
from science_tool.dag.staleness import check_staleness
from science_tool.dag.validate import validate_project


@click.group("dag")
def dag_group() -> None:
    """DAG rendering, numbering, staleness, and audit tools."""


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


@dag_group.command("render")
@click.option(
    "--dag",
    "slug",
    default=None,
    help="Render only this DAG slug. Defaults to all discovered DAGs.",
)
@click.option(
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def render_cmd(slug: str | None, project_path: Path | None) -> None:
    """Render DAG(s) to <slug>-auto.dot and <slug>-auto.png."""
    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        if slug is not None:
            render_one(paths.dag_dir, slug)
            click.echo(f"Rendered {slug}-auto.dot")
        else:
            render_all(paths)
            click.echo("Rendered all DAGs.")
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc


# ---------------------------------------------------------------------------
# number
# ---------------------------------------------------------------------------


@dag_group.command("number")
@click.option(
    "--dag",
    "slug",
    default=None,
    help="Number only this DAG slug. Defaults to all discovered DAGs.",
)
@click.option(
    "--force-stubs",
    is_flag=True,
    default=False,
    help="Overwrite existing edges.yaml stubs (resets curation).",
)
@click.option(
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def number_cmd(slug: str | None, force_stubs: bool, project_path: Path | None) -> None:
    """Assign sequential edge IDs and write <slug>-numbered.dot."""
    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        if slug is not None:
            number_one(paths.dag_dir, slug, force_stubs=force_stubs)
            click.echo(f"Numbered {slug}-numbered.dot")
        else:
            number_all(paths, force_stubs=force_stubs)
            click.echo("Numbered all DAGs.")
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc


# ---------------------------------------------------------------------------
# staleness
# ---------------------------------------------------------------------------


@dag_group.command("staleness")
@click.option(
    "--recent-days",
    default=28,
    show_default=True,
    help="Look-back window in days for unpropagated-task detection.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON to stdout.",
)
@click.option(
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
@click.pass_context
def staleness_cmd(ctx: click.Context, recent_days: int, as_json: bool, project_path: Path | None) -> None:
    """Report drift, under-reviewed edges, and unpropagated tasks."""
    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    report = check_staleness(paths, recent_days=recent_days)

    if as_json:
        click.echo(json.dumps(report.to_json(), indent=2))
    else:
        _print_staleness_summary(report)

    ctx.exit(1 if report.has_findings else 0)


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


@dag_group.command("audit")
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Execute mutations: open review tasks, write unpropagated-task log.",
)
@click.option(
    "--recent-days",
    default=28,
    show_default=True,
    help="Look-back window in days for unpropagated-task detection.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON to stdout.",
)
@click.option(
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
@click.pass_context
def audit_cmd(
    ctx: click.Context,
    fix: bool,
    recent_days: int,
    as_json: bool,
    project_path: Path | None,
) -> None:
    """Run full DAG audit (re-render + staleness). Use --fix to open tasks."""
    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    audit = run_audit(paths, recent_days=recent_days, fix=fix)

    if as_json:
        click.echo(json.dumps(audit.to_json(), indent=2))
    else:
        _print_staleness_summary(audit.staleness)
        if fix and audit.mutations:
            click.echo(f"\nApplied {len(audit.mutations)} mutation(s):")
            for mutation in audit.mutations:
                click.echo(f"  [{mutation.kind}] {mutation.description}")

    ctx.exit(1 if audit.has_findings else 0)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@dag_group.command("init")
@click.argument("slug")
@click.option(
    "--label",
    default=None,
    help="Human-readable label for the DAG (default: slug).",
)
@click.option(
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def init_cmd(slug: str, label: str | None, project_path: Path | None) -> None:
    """Scaffold a new DAG stub: <slug>.dot + <slug>.edges.yaml."""
    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        init_dag(paths.dag_dir, slug, label=label)
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc

    dot_path = paths.dag_dir / f"{slug}.dot"
    yaml_path = paths.dag_dir / f"{slug}.edges.yaml"
    click.echo(f"Created {dot_path.relative_to(project)}")
    click.echo(f"Created {yaml_path.relative_to(project)}")
    click.echo("")
    click.echo(f"Next steps: add nodes and edges to {slug}.dot, then run:")
    click.echo(f"  science-tool dag number --dag {slug}")
    click.echo(f"  science-tool dag render  --dag {slug}")


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------


@dag_group.command("schema")
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write the JSON Schema to this file; default: stdout.",
)
def schema_cmd(output_path: Path | None) -> None:
    """Emit the JSON Schema for edges.yaml files."""
    schema = EdgesYamlFile.model_json_schema()
    canonical = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if output_path is None:
        click.echo(canonical, nl=False)
    else:
        output_path.write_text(canonical, encoding="utf-8")
        click.echo(f"Wrote {output_path}")


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@dag_group.command("validate")
@click.option("--strict", is_flag=True, default=False, help="Enable strict curation gates.")
@click.option(
    "--dag",
    "slug",
    default=None,
    help="Scope to one DAG slug. Defaults to every discovered DAG.",
)
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit machine-readable JSON.")
@click.option(
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def validate_cmd(strict: bool, slug: str | None, as_json: bool, project_path: Path | None) -> None:
    """Validate DAG YAML + .dot files for schema, topology, and curation."""
    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    # Scope to a single DAG if --dag is given.
    if slug is not None:
        paths = DagPaths(
            dag_dir=paths.dag_dir,
            tasks_dir=paths.tasks_dir,
            dags=(slug,),
        )

    report = validate_project(paths, strict=strict)

    if as_json:
        click.echo(json.dumps(report.to_json(), indent=2, sort_keys=True))
    else:
        if report.ok:
            click.echo("dag validate: OK")
        else:
            for f in report.findings:
                blocking = f.severity == "error" or (strict and f.severity == "strict_error")
                prefix = "ERROR" if blocking else "warn"
                loc = f.location or ""
                where = f"{f.dag}#{f.edge_id}" if f.edge_id else f.dag or "<project>"
                click.echo(f"{prefix}: [{f.rule}] {where} ({loc}): {f.message}")

    _sys.exit(0 if report.ok else 1)


# ---------------------------------------------------------------------------
# Internal display helpers
# ---------------------------------------------------------------------------


def _print_staleness_summary(report: object) -> None:  # type: ignore[type-arg]
    """Print a human-readable staleness summary to stdout."""
    from science_tool.dag.staleness import StalenessReport

    assert isinstance(report, StalenessReport)

    drifted = len(report.drifted_edges)
    under = len(report.under_reviewed_edges)
    unresolved = len(report.unresolved_refs)
    unpropagated = len(report.unpropagated_tasks)

    if not report.has_findings and not under:
        click.echo("DAG staleness: no findings.")
        return

    click.echo(f"DAG staleness report ({report.today.isoformat()}, window={report.recent_days}d):")
    click.echo(f"  Drifted edges:       {drifted}")
    click.echo(f"  Under-reviewed:      {under}")
    click.echo(f"  Unresolved refs:     {unresolved}")
    click.echo(f"  Unpropagated tasks:  {unpropagated}")

    if report.drifted_edges:
        click.echo("\nDrifted edges:")
        for edge in report.drifted_edges:
            last = edge.last_cited_date.isoformat() if edge.last_cited_date else "never"
            click.echo(f"  {edge.dag}#{edge.id}  ({edge.source} -> {edge.target})  last cited: {last}")

    if report.unresolved_refs:
        click.echo("\nUnresolved refs:")
        for ref in report.unresolved_refs:
            click.echo(f"  {ref.dag}#{ref.edge_id}  [{ref.kind}] {ref.value}  — {ref.reason}")

    if report.unpropagated_tasks:
        click.echo("\nUnpropagated tasks:")
        for task in report.unpropagated_tasks:
            click.echo(f"  {task.id}  {task.title}")
