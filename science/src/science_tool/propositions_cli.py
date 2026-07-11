"""`science propositions` command group — source-authored proposition CRUD."""

from __future__ import annotations

import click

from science_tool.output import OUTPUT_FORMATS
from science_tool.typed_entity_cli import create_typed_entity, list_typed_entities, show_typed_entity


@click.group("propositions")
def proposition_group() -> None:
    """Proposition source commands."""


@proposition_group.command("create")
@click.argument("title")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
def proposition_create(
    title: str,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
) -> None:
    """Create a source-authored proposition."""

    create_typed_entity(
        kind="proposition",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(related_refs),
        source_refs=list(source_refs),
        with_sections=list(with_sections),
        without_sections=list(without_sections),
        no_hints=no_hints,
    )


@proposition_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def proposition_show(ref: str, output_format: str) -> None:
    """Show a source-authored proposition."""
    show_typed_entity("proposition", ref, output_format)


@proposition_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def proposition_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored propositions."""
    list_typed_entities("proposition", status, related, output_format)
