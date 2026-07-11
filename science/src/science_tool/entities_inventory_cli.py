"""`science entities` command group — inventory and audit of entity trees."""
from __future__ import annotations

from pathlib import Path

import click

from science_tool.entities_inventory import build_inventory
from science_tool.entity_kinds import register_local_kind
from science_tool.entity_migrations import audit_identifiers
from science_tool.output import emit
from science_tool.project_config import project_config_path


@click.group("entities")
def entities_group() -> None:
    """Inspect and audit Science entity inventories."""


@entities_group.command("inventory")
@click.option(
    "--project-root",
    "--project",
    "project_path",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Project root to inventory (legacy alias; default: current working directory).",
)
@click.option("--format", "output_format", type=click.Choice(["json"]), default="json")
@click.option("--output", type=click.Path(path_type=Path), default=None)
def entities_inventory_command(
    project_path: Path,
    output_format: str,
    output: Path | None,
) -> None:
    """Emit the versioned Science entity inventory for a project."""
    inventory = build_inventory(project_path)
    rendered = inventory.model_dump_json(indent=2) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        output.write_text(rendered, encoding="utf-8")


@entities_group.command("audit-identifiers")
@click.option(
    "--project-root",
    "--project",
    "project_path",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Project root to audit (legacy alias; default: current working directory).",
)
def entities_audit_identifiers_command(project_path: Path) -> None:
    emit(output_format="json", payload=audit_identifiers(project_path), render_text=lambda: None)


@entities_group.command("mark-superseded")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_mark_superseded_command(project_root: Path, apply_changes: bool) -> None:
    """Auto-derive `superseded` status from linear supersedes chains (report, then --apply)."""
    from science_tool.consolidation import mark_superseded

    report = mark_superseded(project_root, apply=apply_changes)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_group.command("archive")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--status", "statuses", multiple=True, help="Statuses to archive (default: superseded, archived).")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_archive_command(project_root: Path, statuses: tuple[str, ...], apply_changes: bool) -> None:
    """Relocate hidden-status entities into entities/_archive/ (report, then --apply)."""
    from datetime import datetime, timezone

    from science_tool.archive import DEFAULT_ARCHIVE_STATUSES, archive_entities

    status_set = frozenset(statuses) if statuses else DEFAULT_ARCHIVE_STATUSES
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = archive_entities(project_root, statuses=status_set, apply=apply_changes, now=now)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_group.command("unarchive")
@click.argument("ids", nargs=-1, required=True)
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_unarchive_command(ids: tuple[str, ...], project_root: Path, apply_changes: bool) -> None:
    """Restore archived entities to their original path (report, then --apply)."""
    from datetime import datetime, timezone

    from science_tool.archive import unarchive_entities

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = unarchive_entities(project_root, list(ids), apply=apply_changes, now=now)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_group.group("consolidate")
def entities_consolidate_group() -> None:
    """Collapse a cluster of entities into one cluster-digest (scaffold, then apply)."""


@entities_consolidate_group.command("scaffold")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option(
    "--into",
    "digest_id",
    required=True,
    help="Canonical synthesis id to mint for the cluster-digest (e.g. synthesis:0001-slug).",
)
@click.option("--members", required=True, help="Comma-separated member entity ids.")
@click.option("--title", default=None, help="Digest title (default: derived placeholder).")
def entities_consolidate_scaffold_command(project_root: Path, digest_id: str, members: str, title: str | None) -> None:
    """Mint a cluster-digest stub with consolidates relations (touches no members)."""
    from science_tool.consolidate import scaffold_digest

    member_ids = [m.strip() for m in members.split(",") if m.strip()]
    report = scaffold_digest(project_root, digest_id=digest_id, member_ids=member_ids, title=title or digest_id)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_consolidate_group.command("apply")
@click.argument("digest_id")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Apply changes (default: dry-run report).")
def entities_consolidate_apply_command(digest_id: str, project_root: Path, apply_changes: bool) -> None:
    """Demote + relocate the digest's consolidated members (report, then --apply)."""
    from datetime import datetime, timezone

    from science_tool.consolidate import apply_consolidation

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = apply_consolidation(project_root, digest_id, apply=apply_changes, now=now)
    emit(output_format="json", payload=report, render_text=lambda: None)


@entities_group.command("generate-decisions")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Project root (default: current directory).",
)
@click.option("--write", "write_changes", is_flag=True, help="Write core/decisions.md (default: print).")
def entities_generate_decisions_command(project_root: Path, write_changes: bool) -> None:
    """Render core/decisions.md from entities/decision/*.md (generated view, §B5)."""
    import yaml as _yaml

    from science_tool.graph.decision_log import (
        DECISIONS_REL,
        read_decision_owners,
        render_decisions_view,
    )

    _manifest = _yaml.safe_load(project_config_path(project_root).read_text(encoding="utf-8")) or {}
    _v = _manifest.get("layout_version")
    version = _v if isinstance(_v, int) else None
    if version is None or version < 3:
        raise click.ClickException(
            f"generate-decisions needs an `entities/decision/` owner root, but this project is "
            f"layout_version {version}. This Science version supports layout_version 3 only; "
            f"the v2 layout is no longer supported."
        )

    owners = read_decision_owners(project_root / "entities" / "decision")
    rendered = render_decisions_view(owners)
    if write_changes:
        out = project_root / DECISIONS_REL
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
        click.echo(f"wrote {DECISIONS_REL} ({len(owners)} decisions)")
    else:
        click.echo(rendered)


@entities_group.command("register-kind")
@click.argument("kind")
@click.option("--class", "entity_class", required=True)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Project root whose local profile should be updated (legacy alias; default: current working directory).",
)
def entities_register_kind_command(kind: str, entity_class: str, project_path: Path) -> None:
    """Register a project-local entity kind in the local profile."""
    try:
        result = register_local_kind(project_path, kind, entity_class)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"{kind}: {result}")
