"""`science entity` command group — source-authored entity CRUD."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from science_tool.entities import (
    EntityCommandError,
    EntityRemovalPlan,
    append_entity_note,
    create_entity,
    edit_entity,
    find_entity,
    graph_is_stale,
    list_entities,
    plan_entity_removal,
    remove_entity,
)
from science_tool.graph.store import DEFAULT_GRAPH_PATH, query_neighborhood
from science_tool.output import OUTPUT_FORMATS, emit_query_rows
from science_tool.styles import entity_table_renderers
from science_tool.typed_entity_cli import emit_entity_show, emit_entity_warnings


@click.group("entity")
def entity_group() -> None:
    """Create, edit, note, list, and inspect source-authored entities."""


@entity_group.command("create")
@click.argument("kind")
@click.argument("title")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--path", "explicit_path", type=click.Path(path_type=Path))
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
def entity_create(
    kind: str,
    title: str,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    explicit_path: Path | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
) -> None:
    """Create a source-authored entity markdown file."""

    try:
        result = create_entity(
            project_root=Path.cwd(),
            kind=kind,
            title=title,
            entity_id=entity_id,
            slug=slug,
            explicit_path=explicit_path,
            status=status,
            related=list(related_refs),
            source_refs=list(source_refs),
            with_sections=list(with_sections),
            without_sections=list(without_sections),
            no_hints=no_hints,
        )
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created {result.entity_id} at {result.path.relative_to(Path.cwd())}")
    emit_entity_warnings(result.warnings)


@entity_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_show(ref: str, output_format: str) -> None:
    """Show a source-authored entity."""

    try:
        location = find_entity(Path.cwd(), ref)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    emit_entity_show(location, output_format)


@entity_group.command("edit")
@click.argument("ref")
@click.option("--title")
@click.option("--status")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--updated")
def entity_edit(
    ref: str,
    title: str | None,
    status: str | None,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    updated: str | None,
) -> None:
    """Edit source-authored entity metadata."""

    try:
        result = edit_entity(
            Path.cwd(),
            ref,
            title=title,
            status=status,
            related=list(related_refs),
            source_refs=list(source_refs),
            updated=_parse_entity_date(updated) if updated else None,
        )
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Updated {result.entity_id} at {result.path.relative_to(Path.cwd())}")
    emit_entity_warnings(result.warnings)


@entity_group.command("note")
@click.argument("ref")
@click.argument("note")
@click.option("--date", "note_date")
def entity_note(ref: str, note: str, note_date: str | None) -> None:
    """Append a dated note to a source-authored entity."""

    from datetime import date as _date

    try:
        date_value = _parse_entity_date(note_date) if note_date else None
        result = append_entity_note(Path.cwd(), ref, note, note_date=date_value)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    display_date = (date_value or _date.today()).isoformat()
    click.echo(f"Added note to {result.entity_id} ({display_date})")
    emit_entity_warnings(result.warnings)


@entity_group.command("remove")
@click.argument("target")
@click.option("--apply", "apply_changes", is_flag=True, default=False, help="Delete the entity and safe references.")
def entity_remove(target: str, apply_changes: bool) -> None:
    """Preview or remove an entity file and safely removable references."""

    try:
        plan = remove_entity(Path.cwd(), target) if apply_changes else plan_entity_removal(Path.cwd(), target)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    _emit_entity_removal_plan(plan, applied=apply_changes)


@entity_group.command("list")
@click.argument("kind_arg", required=False)
@click.option("--kind")
@click.option("--status")
@click.option("--related")
@click.option(
    "--include-hidden", is_flag=True, default=False, help="Include superseded/archived entities (hidden by default)."
)
@click.option(
    "--include-archived",
    is_flag=True,
    default=False,
    help="Include archived (relocated) entities from the archive index.",
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_list(
    kind_arg: str | None,
    kind: str | None,
    status: str | None,
    related: str | None,
    include_hidden: bool,
    include_archived: bool,
    output_format: str,
) -> None:
    """List source-authored entities."""

    if kind_arg is not None:
        if kind is not None and kind != kind_arg:
            raise click.ClickException(f"positional kind {kind_arg!r} conflicts with --kind {kind!r}")
        kind = kind_arg
    try:
        rows = list_entities(
            Path.cwd(),
            kind=kind,
            status=status,
            related=related,
            include_hidden=include_hidden,
            include_archived=include_archived,
        )
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    emit_query_rows(
        output_format=output_format,
        title="Entities",
        columns=[("id", "ID"), ("kind", "Kind"), ("status", "Status"), ("title", "Title"), ("path", "Path")],
        rows=rows,
        renderers=entity_table_renderers(),
    )


@entity_group.command("sections")
@click.argument("kind")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_sections(kind: str, output_format: str) -> None:
    """List template sections for a source-authored entity kind."""

    from science_model.templates import MIGRATED_KINDS, EntityTemplateError, Renderer

    if kind not in MIGRATED_KINDS:
        supported = ", ".join(sorted(MIGRATED_KINDS))
        raise click.ClickException(
            f"Kind '{kind}' has no inspectable section template. "
            f"Kinds with declared sections: {supported}. "
            "Other kinds are created with a fixed Summary/Notes body — use `science entity create` directly."
        )

    try:
        sections = Renderer().sections(kind)
    except EntityTemplateError as exc:
        raise click.ClickException(str(exc)) from exc
    frontmatter_rows = _entity_frontmatter_section_rows(kind)
    body_rows = [
        {
            "area": "body",
            "key": section.key,
            "required": "required" if section.required else "optional",
            "name": section.name,
            "type": None,
            "constraints": {},
            "hint": section.hint[:80],
        }
        for section in sections
    ]
    rows = [*frontmatter_rows, *body_rows]
    columns = [
        ("key", "KEY"),
        ("required", "REQ?"),
        ("name", "NAME"),
        ("hint", "HINT"),
    ]
    if output_format == "json" or frontmatter_rows:
        columns = [
            ("area", "AREA"),
            ("key", "KEY"),
            ("required", "REQ?"),
            ("name", "NAME"),
            ("type", "TYPE"),
            ("constraints", "CONSTRAINTS"),
            ("hint", "HINT"),
        ]
    emit_query_rows(
        output_format=output_format,
        title=f"{kind} Template Sections",
        columns=columns,
        rows=rows,
        renderers={
            "type": lambda value, _row: "" if value is None else str(value),
            "constraints": lambda value, _row: _format_frontmatter_constraints(value),
        },
    )


def _entity_frontmatter_section_rows(kind: str) -> list[dict[str, Any]]:
    from science_model.entity_schema import (
        ProfileParseError,
        default_profile_for_kind,
        read_effective_frontmatter_fields,
    )

    try:
        fields = read_effective_frontmatter_fields(default_profile_for_kind(kind))
    except ProfileParseError:
        return []
    return [
        {
            "area": "frontmatter",
            "key": field.key,
            "required": "required" if field.required else "optional",
            "name": field.key,
            "type": field.type,
            "constraints": field.constraints,
            "hint": "",
        }
        for field in fields
    ]


def _format_frontmatter_constraints(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    if "const" in value:
        return f"const={value['const']}"
    if "enum" in value:
        return "enum=" + "|".join(str(item) for item in value["enum"])
    parts: list[str] = []
    for key in ("pattern", "patterns", "format", "formats"):
        if key in value:
            constraint = value[key]
            if isinstance(constraint, list):
                rendered = "&".join(str(item) for item in constraint)
            else:
                rendered = str(constraint)
            parts.append(f"{key}={rendered}")
    return "; ".join(parts)


@entity_group.command("neighbors")
@click.argument("ref")
@click.option("--hops", type=int, default=2, show_default=True)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_neighbors(ref: str, hops: int, output_format: str) -> None:
    """Show graph neighbors for a source-authored entity."""

    try:
        location = find_entity(Path.cwd(), ref)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    if graph_is_stale(Path.cwd(), DEFAULT_GRAPH_PATH):
        click.echo("WARNING: graph materialization may be stale; results below could miss recent edits.", err=True)
    rows = query_neighborhood(
        graph_path=DEFAULT_GRAPH_PATH,
        center=location.entity_id,
        hops=hops,
        graph_layer="graph/knowledge",
        limit=200,
    )
    emit_query_rows(
        output_format=output_format,
        title="Entity Neighbors",
        columns=[("subject", "Subject"), ("predicate", "Predicate"), ("object", "Object")],
        rows=rows,
    )


@entity_group.command("review")
@click.argument("ref")
@click.option(
    "--note",
    default=None,
    help="Required review artifact: the finding, prose diff, created task, or a "
    "reasoned 'no change'. A review without a recorded artifact is rejected.",
)
def entity_review(ref: str, note: str | None) -> None:
    """Mark an epistemic entity as reviewed-as-of today.

    A review must record an artifact via --note; a bare timestamp bump is
    rejected to prevent review-theater (see epistemic-drift-detection design M1).
    """
    from science_tool.entity_review import ReviewError, review_entity

    try:
        path, changed = review_entity(Path.cwd(), ref, note=note, require_artifact=True)
    except ReviewError as exc:
        raise click.ClickException(str(exc)) from exc
    rel = path.relative_to(Path.cwd())
    if changed:
        click.echo(f"Reviewed {ref} -> {rel}")
    else:
        click.echo(f"Reviewed {ref} -> {rel} (no changes)")


@entity_group.command("needs-review")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
def entity_needs_review(output_format: str) -> None:
    """List epistemic entities flagged needs-review or stale by the materialized graph."""
    from science_tool.entity_review import list_needs_review
    from science_tool.output import emit_query_rows

    rows = list_needs_review(Path.cwd())
    emit_query_rows(
        output_format=output_format,
        title="Entities needing review",
        columns=[("state", "State"), ("kind", "Kind"), ("id", "ID")],
        rows=rows,
    )


def _emit_entity_removal_plan(plan: EntityRemovalPlan, *, applied: bool) -> None:
    action = "Removed" if applied else "DRY RUN"
    click.echo(f"{action} {plan.entity_id}")
    click.echo(f"- delete {plan.rel_path}")
    if plan.safe_hits:
        click.echo("- safe structured reference cleanup:")
        for hit in sorted(plan.safe_hits, key=lambda item: (item.rel_path, item.line, item.detail)):
            click.echo(f"  - {hit.rel_path}:{hit.line}: {hit.detail}")
    else:
        click.echo("- safe structured reference cleanup: none")
    if plan.manual_hits:
        click.echo("- manual references:")
        for hit in sorted(plan.manual_hits, key=lambda item: (item.rel_path, item.line, item.detail)):
            click.echo(f"  - {hit.rel_path}:{hit.line}: {hit.detail}")
    else:
        click.echo("- manual references: none")
    if not applied:
        click.echo("Run with --apply to delete the entity and rewrite safe structured references.")


def _parse_entity_date(value: str) -> Any:
    from datetime import date

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise click.ClickException(f"Invalid date: {value}") from exc
