from __future__ import annotations

from pathlib import Path

import click

from science_tool.data_audit import audit_project, audit_project_notes, render_json
from science_tool.data_audit_fix import apply_fixes
from science_tool.project_config import load_project_config, resolve_data_policy


@click.group("data")
def data_group() -> None:
    """Audit the data/results/entities tracking boundary."""


@data_group.command("audit")
@click.option(
    "--project-root",
    "--project",
    "project_path",
    type=click.Path(path_type=Path),
    default=None,
    envvar="SCIENCE_PROJECT_ROOT",
    help="Project root (defaults to $SCIENCE_PROJECT_ROOT or cwd).",
)
@click.option(
    "--fix",
    is_flag=True,
    default=False,
    help="Relocate stranded records data/ → results/ (stages, never commits).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit the machine-readable move report.",
)
def data_audit_command(project_path: Path | None, fix: bool, output_format: str, as_json: bool) -> None:
    """Report (and optionally fix) data/results/entities boundary violations."""
    emit_json = as_json or output_format == "json"
    project_path = project_path or Path.cwd()  # runtime default; honors the env var above
    try:
        policy = resolve_data_policy(load_project_config(project_path))
    except FileNotFoundError:
        from science_tool.data_policy import DEFAULT_DATA_POLICY

        policy = DEFAULT_DATA_POLICY
    violations = audit_project(project_path, policy)
    notes = audit_project_notes(project_path)

    if fix:
        outcomes = apply_fixes(project_path, violations)
        if emit_json:
            click.echo(render_json(violations, outcomes, notes), nl=False)
        else:
            performed = sum(1 for o in outcomes if o.performed)
            flagged = sum(1 for o in outcomes if not o.performed)
            for o in outcomes:
                mark = "moved" if o.performed else "FLAG"
                tgt = o.violation.proposed_target or "-"
                click.echo(f"  [{mark}] {o.violation.path} → {tgt}" + (f"  ({o.reason})" if o.reason else ""))
            click.echo(f"\n{performed} moved (staged, not committed), {flagged} flagged.")
        return

    if emit_json:
        click.echo(render_json(violations, notes=notes), nl=False)
    else:
        for note in notes:
            click.echo(f"  [{note.severity}:{note.code}] {note.message}")
        if not violations:
            click.echo("clean: no data/results boundary violations.")
        for v in violations:
            tgt = v.proposed_target or "-"
            click.echo(f"  [{v.quadrant.value}] {v.path} → {tgt}")
    if violations:
        raise SystemExit(1)
