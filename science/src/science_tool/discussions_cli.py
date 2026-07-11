"""`science discussions` command group — source-authored discussion CRUD."""

from __future__ import annotations

import click

from science_tool.output import OUTPUT_FORMATS
from science_tool.typed_entity_cli import create_typed_entity, list_typed_entities, show_typed_entity


@click.group("discussions")
def discussion_group() -> None:
    """Discussion source commands."""


@discussion_group.command("create")
@click.argument("title")
@click.option("--focus", "focus_refs", multiple=True, help="Focus entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
def discussion_create(
    title: str,
    focus_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
) -> None:
    """Create a source-authored discussion."""

    create_typed_entity(
        kind="discussion",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(focus_refs),
        source_refs=list(source_refs),
        with_sections=list(with_sections),
        without_sections=list(without_sections),
        no_hints=no_hints,
    )


@discussion_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def discussion_show(ref: str, output_format: str) -> None:
    """Show a source-authored discussion."""
    show_typed_entity("discussion", ref, output_format)


@discussion_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def discussion_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored discussions."""
    list_typed_entities("discussion", status, related, output_format)
