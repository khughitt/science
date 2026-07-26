"""Click CLI group for the ``dag`` subcommands."""

from __future__ import annotations

import difflib
import sys as _sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from science_tool.dag.audit import run_audit
from science_tool.dag.init import init_dag
from science_tool.dag.number import number_all, number_one
from science_tool.dag.paths import DagPaths, load_dag_paths
from science_tool.dag.render import render_all
from science_tool.dag.validate import validate_project
from science_tool.data_root import project_config_path
from science_tool.output import emit


@click.group("dag")
def dag_group() -> None:
    """DAG rendering, numbering, validation, and audit tools."""


def _wants_json(*, as_json: bool, output_format: str) -> bool:
    return as_json or output_format == "json"


def _validation_finding_blocks(finding: dict[str, Any], *, strict: bool) -> bool:
    return finding["severity"] == "error" or (strict and finding["severity"] == "strict_error")


def _print_validation_findings(findings: list[dict[str, Any]], *, strict: bool, echo: Callable[[str], None]) -> None:
    for finding in findings:
        prefix = "ERROR" if _validation_finding_blocks(finding, strict=strict) else "warn"
        loc = finding.get("location") or ""
        edge_id = finding.get("edge_id")
        where = f"{finding['dag']}#{edge_id}" if edge_id else finding.get("dag") or "<project>"
        echo(f"{prefix}: [{finding['rule']}] {where} ({loc}): {finding['message']}")


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
    epistemic source of truth); ``edge_status`` is DERIVED via
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
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def number_cmd(slug: str | None, project_path: Path | None) -> None:
    """Assign sequential edge IDs and write numbered DOT only."""
    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        if slug is not None:
            number_one(paths.dag_dir, slug)
            click.echo(f"Numbered {slug}-numbered.dot")
        else:
            number_all(paths)
            click.echo("Numbered all DAGs.")
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(str(exc)) from exc


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
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted audit report to PATH instead of stdout.",
)
@click.pass_context
def audit_cmd(
    ctx: click.Context,
    fix: bool,
    strict: bool,
    as_json: bool,
    output_format: str,
    project_path: Path | None,
    output_path: Path | None,
) -> None:
    """Run DAG audit (validate + re-render proposition-backed DAGs)."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.dag.audit_projection import project_dag_audit

    project = (project_path or Path.cwd()).resolve()
    try:
        paths = load_dag_paths(project)
    except (FileNotFoundError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        audit = run_audit(paths, fix=fix, strict=strict)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    effective_format = "json" if _wants_json(as_json=as_json, output_format=output_format) else output_format
    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("dag-audit", effective_format))
    sink = BoundedSink(
        lookup("dag audit"), output_path=output_path, command_path="dag audit", complete_via=complete_via
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete audit report to {output_path}")
        if output_path is not None
        else None
    )

    full = audit.to_json()
    displayed = full if output_path is not None else project_dag_audit(full)
    findings_omitted = displayed["validation"].get("findings_omitted", 0)
    mutations_omitted = displayed.get("mutations_omitted", 0)
    if output_path is None and (findings_omitted or mutations_omitted):
        truncation: dict[str, Any] = {"complete_via": complete_via}
        if findings_omitted:
            truncation["findings"] = {"omitted": findings_omitted, "total": len(full["validation"]["findings"])}
        if mutations_omitted:
            truncation["mutations"] = {"omitted": mutations_omitted, "total": len(full["mutations"])}
        displayed = {**displayed, "truncation": truncation}

    def _render() -> None:
        if full["validation"]["ok"]:
            sink.echo("DAG audit OK.")
        else:
            shown_findings = displayed["validation"]["findings"]
            _print_validation_findings(shown_findings, strict=strict, echo=sink.echo)
            if findings_omitted:
                sink.echo(f"showing {len(shown_findings)} of {findings_omitted + len(shown_findings)} findings")
                sink.echo(f"  complete output:  {complete_via}")
        if fix and full["mutations"]:
            sink.echo(f"\nApplied {len(full['mutations'])} mutation(s):")
            for mutation in displayed["mutations"]:
                sink.echo(f"  [{mutation['kind']}] {mutation['description']}")
            if mutations_omitted:
                sink.echo(f"showing {len(displayed['mutations'])} of {len(full['mutations'])} mutations")
                sink.echo(f"  complete output:  {complete_via}")

    emit(output_format=effective_format, payload=displayed, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)

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
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted validation report to PATH instead of stdout.",
)
def validate_cmd(
    strict: bool,
    slug: str | None,
    as_json: bool,
    output_format: str,
    project_path: Path | None,
    output_path: Path | None,
) -> None:
    """Validate DOT topology against compiled relational propositions."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_single_list_report
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink

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

    effective_format = "json" if _wants_json(as_json=as_json, output_format=output_format) else output_format
    complete_via = build_complete_via(
        click.get_current_context(), output_hint=hint_for("dag-validate", effective_format)
    )
    sink = BoundedSink(
        lookup("dag validate"), output_path=output_path, command_path="dag validate", complete_via=complete_via
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete dag validate report to {output_path}")
        if output_path is not None
        else None
    )

    full = report.to_json()
    displayed = full if output_path is not None else project_single_list_report(full, "findings", 40)
    findings_omitted = displayed.get("findings_omitted", 0)
    if output_path is None and findings_omitted:
        displayed = {
            **displayed,
            "truncation": {"omitted": findings_omitted, "total": len(full["findings"]), "complete_via": complete_via},
        }

    def _render() -> None:
        if full["ok"]:
            sink.echo("dag validate: OK")
        else:
            _print_validation_findings(displayed["findings"], strict=strict, echo=sink.echo)
        if findings_omitted:
            sink.echo(f"showing {len(displayed['findings'])} of {len(full['findings'])} findings")
            sink.echo(f"  complete output:  {complete_via}")

    emit(output_format=effective_format, payload=displayed, render_text=_render, sink=sink, sort_keys=True)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)

    _sys.exit(0 if report.ok else 1)


# ---------------------------------------------------------------------------
# workbench
# ---------------------------------------------------------------------------


@dag_group.command("apply-workbench")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Reviewed workbench YAML path to compile/apply. Relative paths resolve against the project root.",
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
def apply_workbench_cmd(input_path: Path, output_format: str, project_path: Path | None) -> None:
    """Compile a reviewed DAG workbench into entities and canonical YAML."""
    from science_tool.dag.workbench_apply import WorkbenchApplyError, apply_workbench

    project = (project_path or Path.cwd()).resolve()
    try:
        result = apply_workbench(project, input_path=input_path)
    except WorkbenchApplyError as exc:
        raise click.ClickException(str(exc)) from exc

    def _render() -> None:
        action = "Applied" if result.status == "applied" else "No-op"
        click.echo(f"{action} workbench: {result.input_path}")
        click.echo(
            f"  rows={result.row_count}, propositions={result.proposition_count}, "
            f"evidence_lines={result.evidence_line_count}, changed_paths={len(result.changed_paths)}"
        )
        for path in result.changed_paths:
            click.echo(f"  {path}")

    emit(output_format=output_format, payload=result.to_json(), render_text=_render, sort_keys=True)


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
        project_config_path(scratch).write_text(
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
