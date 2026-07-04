"""Click CLI group for the ``dag`` subcommands."""

from __future__ import annotations

import difflib
import json
import sys as _sys
import tempfile
from pathlib import Path

import click

from science_tool.dag.audit import run_audit
from science_tool.dag.init import init_dag
from science_tool.dag.number import number_all, number_one
from science_tool.dag.paths import DagPaths, load_dag_paths
from science_tool.dag.render import render_all
from science_tool.dag.schema import EdgesYamlFile
from science_tool.dag.validate import ValidationFinding, ValidationReport, validate_project


@click.group("dag")
def dag_group() -> None:
    """DAG rendering, numbering, retired-edge inspection, and audit tools."""


def _wants_json(*, as_json: bool, output_format: str) -> bool:
    return as_json or output_format == "json"


def _validation_finding_blocks(finding: ValidationFinding, *, strict: bool) -> bool:
    return finding.severity == "error" or (strict and finding.severity == "strict_error")


def _print_validation_findings(report: ValidationReport, *, strict: bool) -> None:
    for finding in report.findings:
        prefix = "ERROR" if _validation_finding_blocks(finding, strict=strict) else "warn"
        loc = finding.location or ""
        where = f"{finding.dag}#{finding.edge_id}" if finding.edge_id else finding.dag or "<project>"
        click.echo(f"{prefix}: [{finding.rule}] {where} ({loc}): {finding.message}")


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
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def render_cmd(slug: str | None, project_path: Path | None) -> None:
    """Render DAG(s) from compiled relational propositions.

    Edge SEMANTICS are SOURCED from compiled relational propositions (the
    epistemic source-of-truth, Task 5f); ``edge_status`` is DERIVED via
    ``derived_edge_status``. Every DOT edge must have a compiled proposition
    edge.
    """
    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    proposition_edges = _source_proposition_edges(project)

    try:
        if slug is not None:
            paths = DagPaths(
                dag_dir=paths.dag_dir,
                tasks_dir=paths.tasks_dir,
                dags=(slug,),
                project_root=paths.project_root,
            )
            render_all(paths, proposition_edges=proposition_edges)
            click.echo(f"Rendered {slug}-auto.dot")
        else:
            render_all(paths, proposition_edges=proposition_edges)
            click.echo("Rendered all DAGs.")
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc


def _source_proposition_edges(project: Path) -> list[dict]:  # type: ignore[type-arg]
    """Source channel-mode edges from compiled propositions."""
    from science_tool.dag.proposition_edges import load_proposition_edges

    return load_proposition_edges(project)


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
    help="Retired; *.edges.yaml is no longer a DAG authoring surface.",
)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def number_cmd(slug: str | None, force_stubs: bool, project_path: Path | None) -> None:
    """Assign sequential edge IDs and write numbered DOT only."""
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
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
@click.pass_context
def staleness_cmd(
    ctx: click.Context,
    recent_days: int,
    as_json: bool,
    output_format: str,
    project_path: Path | None,
) -> None:
    """Retired YAML staleness command."""
    project = (project_path or Path.cwd()).resolve()
    try:
        load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    del ctx, recent_days, as_json, output_format
    raise click.ClickException(
        "DAG staleness over *.edges.yaml is retired. Run `science dag retired-edges` "
        "to inspect remaining YAML migration content. Proposition-backed freshness "
        "will be designed separately."
    )


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


@dag_group.command("audit")
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="No-op after validation succeeds; refuses validation-blocking findings.",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Enable strict validation gates.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON to stdout.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option(
    "--project-root",
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
    strict: bool,
    as_json: bool,
    output_format: str,
    project_path: Path | None,
) -> None:
    """Run DAG audit (validate + re-render proposition-backed DAGs)."""
    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        audit = run_audit(paths, fix=fix, strict=strict)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    if _wants_json(as_json=as_json, output_format=output_format):
        click.echo(json.dumps(audit.to_json(), indent=2))
    else:
        if audit.validation.ok:
            click.echo("DAG audit OK.")
        else:
            _print_validation_findings(audit.validation, strict=strict)
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
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def init_cmd(slug: str, label: str | None, project_path: Path | None) -> None:
    """Scaffold a new DAG DOT topology file."""
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
    click.echo(f"Created {dot_path.relative_to(project)}")
    click.echo("")
    click.echo("Next steps: add DOT topology, then author matching relational proposition rows in a workbench.")
    click.echo(f"  science dag number --dag {slug}")
    click.echo(f"  science dag render --dag {slug}")


# ---------------------------------------------------------------------------
# retired-edges
# ---------------------------------------------------------------------------


@dag_group.command("retired-edges")
@click.option(
    "--dag",
    "slug",
    default=None,
    help="Inspect one retired DAG edge file. Defaults to every *.edges.yaml file.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def retired_edges_cmd(slug: str | None, output_format: str, project_path: Path | None) -> None:
    """Inspect retired *.edges.yaml files for migration diagnostics."""
    from science_tool.dag.retired_edges import build_retired_edges_report

    project = (project_path or Path.cwd()).resolve()
    report = build_retired_edges_report(project, dag=slug)
    payload = report.to_json()
    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    summary = payload["summary"]
    click.echo(
        "Retired DAG edges: "
        f"{summary['files']} file(s), {summary['edges']} edge(s), "
        f"{summary['migration_worthy_edges']} migration-worthy edge(s)."
    )
    for file in payload["files"]:
        flags = []
        if file["orphan_dot"]:
            flags.append("orphan-dot")
        flag_text = f" [{' '.join(flags)}]" if flags else ""
        click.echo(f"  {file['dag']}: {file['edge_count']} edge(s){flag_text}")


@dag_group.command("retired-edge-migration-plan")
@click.option(
    "--dag",
    "slug",
    default=None,
    help="Plan migration for one retired DAG edge file. Defaults to every *.edges.yaml file.",
)
@click.option(
    "--focal-hypothesis",
    default=None,
    help="Hypothesis ref to use as file-level workbench membership for migrated rows.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "workbench"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def retired_edge_migration_plan_cmd(
    slug: str | None,
    focal_hypothesis: str | None,
    output_format: str,
    project_path: Path | None,
) -> None:
    """Plan read-only migration from retired *.edges.yaml rows to workbench rows."""
    from science_tool.dag.retired_edge_migration import (
        build_retired_edge_migration_plan,
        migration_plan_to_workbench_yaml,
        render_migration_plan_table,
    )

    project = (project_path or Path.cwd()).resolve()
    try:
        plan = build_retired_edge_migration_plan(project, dag=slug, focal_hypothesis=focal_hypothesis)
        if output_format == "json":
            click.echo(json.dumps(plan.to_json(), indent=2, sort_keys=True))
            return
        if output_format == "workbench":
            click.echo(migration_plan_to_workbench_yaml(plan), nl=False)
            return
        click.echo(render_migration_plan_table(plan), nl=False)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


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
    """Emit the JSON Schema for retired edges.yaml migration inspection."""
    schema = EdgesYamlFile.model_json_schema()
    canonical = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    banner = (
        "RETIRED: this schema describes the retired *.edges.yaml migration surface, "
        "not an active DAG authoring input.\n"
    )
    click.echo(banner, nl=False, err=True)
    if output_path is None:
        click.echo(canonical, nl=False)
    else:
        output_path.write_text(canonical, encoding="utf-8")
        click.echo(f"Wrote retired edges.yaml schema to {output_path}")


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
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def validate_cmd(
    strict: bool,
    slug: str | None,
    as_json: bool,
    output_format: str,
    project_path: Path | None,
) -> None:
    """Validate DOT topology against compiled relational propositions."""
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
            project_root=paths.project_root,
        )

    report = validate_project(paths, strict=strict)

    if _wants_json(as_json=as_json, output_format=output_format):
        click.echo(json.dumps(report.to_json(), indent=2, sort_keys=True))
    else:
        if report.ok:
            click.echo("dag validate: OK")
        else:
            _print_validation_findings(report, strict=strict)

    _sys.exit(0 if report.ok else 1)


# ---------------------------------------------------------------------------
# workbench
# ---------------------------------------------------------------------------


@dag_group.command("workbench")
@click.option(
    "--check",
    "check_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Check that the committed workbench file is in canonical form (CI fixpoint gate).",
)
@click.pass_context
def workbench_cmd(ctx: click.Context, check_path: Path | None) -> None:
    """Workbench operations (``--check``: CI fixpoint gate on a scratch graph).

    ``dag workbench --check <file>`` reads the committed workbench YAML,
    compiles it on a throwaway scratch directory (never writes to the real
    entities/ dir), serializes the result to canonical YAML, and diffs the
    canonical form against the committed text.  Exits 0 if they are identical;
    exits 1 with a unified diff if they differ.
    """
    if check_path is None:
        click.echo(ctx.get_help())
        ctx.exit(0)
        return

    import yaml

    from science_tool.dag.workbench import WorkbenchFile, compile_workbench, serialize_canonical

    committed_text = check_path.read_text(encoding="utf-8")

    # Parse + compile on a scratch project root so entity files are written to
    # a throwaway temp dir, never to the real project.
    with tempfile.TemporaryDirectory() as scratch_str:
        scratch = Path(scratch_str)
        # Minimal science.yaml so the entity-layer writer resolves path policies.
        (scratch / "science.yaml").write_text(
            "name: workbench-check-scratch\nknowledge_profiles:\n  local: local\n",
            encoding="utf-8",
        )
        try:
            wb = WorkbenchFile.model_validate(yaml.safe_load(committed_text) or {})
            result = compile_workbench(wb, project_root=scratch)
        except Exception as exc:  # noqa: BLE001
            raise click.ClickException(f"Failed to compile workbench: {exc}") from exc

        canonical_text = serialize_canonical(result)

    if committed_text == canonical_text:
        click.echo("workbench --check: OK (canonical)")
        ctx.exit(0)
        return

    # Produce a readable unified diff.
    diff_lines = list(
        difflib.unified_diff(
            committed_text.splitlines(keepends=True),
            canonical_text.splitlines(keepends=True),
            fromfile=str(check_path),
            tofile="<canonical>",
        )
    )
    diff_text = "".join(diff_lines)
    click.echo(
        f"workbench --check: FAIL — committed file differs from canonical form.\n\n{diff_text}",
        err=False,
    )
    ctx.exit(1)
