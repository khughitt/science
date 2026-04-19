from __future__ import annotations

from pathlib import Path

import click

from science_tool.aspects.migrate import (
    AspectsMigrationConflict,
    apply_migration_plan,
    build_migration_plan,
)


@click.group("aspects")
def aspects_group() -> None:
    """Manage entity aspects — migration and validation helpers."""


@aspects_group.command("migrate")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root (containing tasks/, science.yaml).",
)
@click.option(
    "--apply",
    "apply_flag",
    is_flag=True,
    default=False,
    help="Write changes in place. Without this flag, prints the plan and exits.",
)
def migrate_cmd(project_root: Path, apply_flag: bool) -> None:
    """Migrate legacy task `type: research|dev` fields into `aspects:`."""
    try:
        plan = build_migration_plan(project_root)
    except AspectsMigrationConflict as exc:
        raise click.ClickException(str(exc)) from exc

    if not plan.task_rewrites and not plan.conflicts:
        click.echo("No legacy task entries found. Project is migrated.")
        return

    for rewrite in plan.task_rewrites:
        click.echo(
            f"[{rewrite.task_id}] in {rewrite.source_path.name}: "
            f"-> aspects: {rewrite.new_aspects}"
        )
    for conflict in plan.conflicts:
        click.echo(
            f"[{conflict.task_id}] in {conflict.source_path.name}: "
            f"CONFLICT — {conflict.reason}",
            err=True,
        )

    if not apply_flag:
        click.echo("")
        click.echo(f"Dry run. Re-run with --apply to write {len(plan.task_rewrites)} change(s).")
        return

    apply_migration_plan(plan)
    click.echo("")
    click.echo(f"Applied {len(plan.task_rewrites)} rewrite(s).")
    if plan.conflicts:
        click.echo(f"Skipped {len(plan.conflicts)} conflict(s); resolve manually.")
