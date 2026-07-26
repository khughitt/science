"""`science sync` command group — cross-project sync commands."""
from __future__ import annotations

from pathlib import Path

import click

from science_tool.output import OUTPUT_FORMATS, emit


@click.group("sync")
def sync_group() -> None:
    """Cross-project sync commands."""


@sync_group.command("run")
@click.option("--config", "config_path", type=click.Path(), default=None)
@click.option("--dry-run", is_flag=True, help="Preview without writing changes")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted sync report to PATH instead of stdout.",
)
def sync_run(config_path: str | None, dry_run: bool, output_format: str, output_path: Path | None) -> None:
    """Run cross-project sync."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_single_list_report
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.registry.config import get_default_config_path, load_global_config
    from science_tool.registry.index import get_default_registry_dir
    from science_tool.registry.state import get_default_state_path
    from science_tool.registry.sync import run_sync as do_sync

    cfg_path = Path(config_path) if config_path else get_default_config_path()
    config = load_global_config(cfg_path)

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("sync-run", output_format))
    sink = BoundedSink(lookup("sync run"), output_path=output_path, command_path="sync run", complete_via=complete_via)
    control_notice = (
        bounded_control_notice(f"wrote the complete sync report to {output_path}")
        if output_path is not None
        else None
    )

    if not config.projects:
        full = {
            "dry_run": dry_run,
            "message": "No registered projects. Run science commands in project directories first.",
        }
        emit(output_format=output_format, payload=full, render_text=lambda: sink.echo(full["message"]), sink=sink)
        sink.flush()
        if control_notice is not None:
            click.echo(control_notice)
        return

    registry_dir = get_default_registry_dir()
    state_path = get_default_state_path()
    report = do_sync(
        project_paths=[Path(p.path) for p in config.projects],
        registry_dir=registry_dir,
        state_path=state_path,
        dry_run=dry_run,
    )
    full = {
        "dry_run": dry_run,
        "entities_total": report.entities_total,
        "entities_new": report.entities_new,
        "relations_total": report.relations_total,
        "drift_warnings": list(report.drift_warnings),
    }
    displayed = full if output_path is not None else project_single_list_report(full, "drift_warnings", 40)
    if output_path is None and displayed.get("drift_warnings_omitted", 0):
        displayed = {
            **displayed,
            "truncation": {
                "omitted": displayed["drift_warnings_omitted"],
                "total": len(full["drift_warnings"]),
                "complete_via": complete_via,
            },
        }

    def _render() -> None:
        prefix = "[dry run] " if displayed["dry_run"] else ""
        sink.echo(f"{prefix}Sync complete.")
        sink.echo(f"  Entities: {displayed['entities_total']} (+{displayed['entities_new']} new)")
        sink.echo(f"  Relations: {displayed['relations_total']}")
        warnings = displayed["drift_warnings"]
        if warnings:
            sink.echo("  Drift warnings:")
            for warning in warnings:
                sink.echo(f"    {warning}")
        if displayed.get("drift_warnings_omitted", 0):
            sink.echo(f"  showing {len(warnings)} of {len(full['drift_warnings'])} drift warnings")
            sink.echo(f"    complete output:  {complete_via}")

    emit(output_format=output_format, payload=displayed, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@sync_group.command("status")
@click.option("--config", "config_path", type=click.Path(), default=None)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted sync status to PATH instead of stdout.",
)
def sync_status(config_path: str | None, output_format: str, output_path: Path | None) -> None:
    """Show sync status and staleness."""
    from datetime import datetime

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_single_list_report
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.registry.config import get_default_config_path, load_global_config
    from science_tool.registry.state import load_sync_state

    cfg_path = Path(config_path) if config_path else get_default_config_path()
    config = load_global_config(cfg_path)
    state_path = cfg_path.parent / "sync_state.yaml"
    state = load_sync_state(state_path)

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("sync-status", output_format))
    sink = BoundedSink(
        lookup("sync status"), output_path=output_path, command_path="sync status", complete_via=complete_via
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete sync status to {output_path}")
        if output_path is not None
        else None
    )

    if state.last_sync is None:
        full = {"last_sync": None, "registered_count": len(config.projects)}

        def _render_no_sync() -> None:
            sink.echo("No sync has been performed yet.")
            if config.projects:
                sink.echo(f"  {len(config.projects)} registered project(s). Run `science sync run`.")

        emit(output_format=output_format, payload=full, render_text=_render_no_sync, sink=sink)
        sink.flush()
        if control_notice is not None:
            click.echo(control_notice)
        return

    days = (datetime.now() - state.last_sync).days
    stale_threshold = config.sync.stale_after_days
    project_rows = [
        {"name": name, "entity_count": pstate.entity_count, "entity_hash": pstate.entity_hash}
        for name, pstate in state.projects.items()
    ]
    full = {
        "last_sync": state.last_sync.isoformat(),
        "days_since_sync": days,
        "stale": days > stale_threshold,
        "stale_threshold_days": stale_threshold,
        "projects": project_rows,
    }
    displayed = full if output_path is not None else project_single_list_report(full, "projects", 40)
    if output_path is None and displayed.get("projects_omitted", 0):
        displayed = {
            **displayed,
            "truncation": {
                "omitted": displayed["projects_omitted"],
                "total": len(full["projects"]),
                "complete_via": complete_via,
            },
        }

    def _render() -> None:
        sink.echo(f"Last sync: {displayed['last_sync']} ({displayed['days_since_sync']} days ago)")
        if displayed["stale"]:
            sink.echo(
                f"  Sync is stale (threshold: {displayed['stale_threshold_days']} days). Run `science sync run`."
            )
        for row in displayed["projects"]:
            sink.echo(f"  {row['name']}: {row['entity_count']} entities (hash: {row['entity_hash'][:8]})")
        if displayed.get("projects_omitted", 0):
            sink.echo(f"  showing {len(displayed['projects'])} of {len(full['projects'])} projects")
            sink.echo(f"    complete output:  {complete_via}")

    emit(output_format=output_format, payload=displayed, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@sync_group.command("projects")
@click.option("--config", "config_path", type=click.Path(), default=None)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted payload to PATH instead of stdout.",
)
def sync_projects(config_path: str | None, output_format: str, output_path: Path | None) -> None:
    """List registered projects."""
    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_rows
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.registry.config import get_default_config_path, load_global_config

    cfg_path = Path(config_path) if config_path else get_default_config_path()
    config = load_global_config(cfg_path)

    sink = BoundedSink(
        lookup("sync projects"),
        output_path=output_path,
        command_path="sync projects",
        complete_via=build_complete_via(click.get_current_context(), output_hint=hint_for("sync-projects", output_format)),
    )
    control_notice = (
        bounded_control_notice(f"wrote {len(config.projects)} projects to {output_path}")
        if output_path is not None
        else None
    )

    rows = [{"name": p.name, "path": p.path, "registered": str(p.registered)} for p in config.projects]
    projected = project_rows(rows, sink.max_rows)
    displayed = projected.rows
    payload: dict[str, object] = {"projects": displayed}
    if projected.truncated:
        payload["truncation"] = {
            "omitted": projected.omitted,
            "total": projected.total,
            "complete_via": sink.complete_via,
        }

    def _render() -> None:
        if not rows:
            sink.echo("No registered projects.")
            return
        for row in displayed:
            sink.echo(f"  {row['name']}: {row['path']} (registered {row['registered']})")
        if projected.truncated:
            sink.echo(f"showing {len(displayed)} of {projected.total} project(s)")
            sink.echo(f"  complete output:  {sink.complete_via}")

    emit(output_format=output_format, payload=payload, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)


@sync_group.command("rebuild")
@click.option("--config", "config_path", type=click.Path(), default=None)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the complete, unbudgeted rebuild report to PATH instead of stdout.",
)
def sync_rebuild(config_path: str | None, output_format: str, output_path: Path | None) -> None:
    """Rebuild registry from scratch by scanning all projects."""
    import shutil

    from science_tool.budget.control import bounded_control_notice
    from science_tool.budget.invocation import build_complete_via, hint_for
    from science_tool.budget.projection import project_single_list_report
    from science_tool.budget.registry import lookup
    from science_tool.budget.sink import BoundedSink
    from science_tool.registry.config import get_default_config_path, load_global_config, prune_missing_projects
    from science_tool.registry.index import get_default_registry_dir
    from science_tool.registry.state import get_default_state_path
    from science_tool.registry.sync import run_sync as do_sync

    cfg_path = Path(config_path) if config_path else get_default_config_path()
    registry_dir = get_default_registry_dir()
    state_path = get_default_state_path()

    complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("sync-rebuild", output_format))
    sink = BoundedSink(
        lookup("sync rebuild"), output_path=output_path, command_path="sync rebuild", complete_via=complete_via
    )
    control_notice = (
        bounded_control_notice(f"wrote the complete rebuild report to {output_path}")
        if output_path is not None
        else None
    )

    pruned = prune_missing_projects(cfg_path)
    config = load_global_config(cfg_path)

    if not config.projects:
        full = {"pruned": pruned, "message": "No registered projects."}
        displayed = full if output_path is not None else project_single_list_report(full, "pruned", 40)
        if output_path is None and displayed.get("pruned_omitted", 0):
            displayed = {
                **displayed,
                "truncation": {
                    "omitted": displayed["pruned_omitted"],
                    "total": len(full["pruned"]),
                    "complete_via": complete_via,
                },
            }

        def _render_no_projects() -> None:
            for path in displayed["pruned"]:
                sink.echo(f"Pruned missing project: {path}")
            sink.echo(displayed["message"])
            if displayed.get("pruned_omitted", 0):
                sink.echo(f"  showing {len(displayed['pruned'])} of {len(full['pruned'])} pruned")
                sink.echo(f"    complete output:  {complete_via}")

        emit(output_format=output_format, payload=displayed, render_text=_render_no_projects, sink=sink)
        sink.flush()
        if control_notice is not None:
            click.echo(control_notice)
        return

    if registry_dir.is_dir():
        shutil.rmtree(registry_dir)

    report = do_sync(
        project_paths=[Path(p.path) for p in config.projects],
        registry_dir=registry_dir,
        state_path=state_path,
    )
    full = {
        "pruned": pruned,
        "entities_total": report.entities_total,
        "relations_total": report.relations_total,
    }
    displayed = full if output_path is not None else project_single_list_report(full, "pruned", 40)
    if output_path is None and displayed.get("pruned_omitted", 0):
        displayed = {
            **displayed,
            "truncation": {
                "omitted": displayed["pruned_omitted"],
                "total": len(full["pruned"]),
                "complete_via": complete_via,
            },
        }

    def _render() -> None:
        for path in displayed["pruned"]:
            sink.echo(f"Pruned missing project: {path}")
        sink.echo("Registry cleared. Rebuilding...")
        sink.echo(f"Rebuild complete. {displayed['entities_total']} entities, {displayed['relations_total']} relations.")
        if displayed.get("pruned_omitted", 0):
            sink.echo(f"  showing {len(displayed['pruned'])} of {len(full['pruned'])} pruned")
            sink.echo(f"    complete output:  {complete_via}")

    emit(output_format=output_format, payload=displayed, render_text=_render, sink=sink)
    sink.flush()
    if control_notice is not None:
        click.echo(control_notice)
