"""`science hypotheses` command group — source-authored hypothesis CRUD."""

from __future__ import annotations

import click

from science_tool.output import OUTPUT_FORMATS
from science_tool.typed_entity_cli import (
    build_origin_frontmatter,
    create_typed_entity,
    list_typed_entities,
    show_typed_entity,
)


@click.group("hypotheses")
def hypothesis_group() -> None:
    """Hypothesis source commands."""


@hypothesis_group.command("create")
@click.argument("title")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option(
    "--phase",
    type=click.Choice(["active", "candidate"]),
    default="active",
    show_default=True,
    help="candidate trial framing (includes Promotion criteria) or committed active frame",
)
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
@click.option(
    "--origin",
    "origins",
    multiple=True,
    help="Origin as TYPE[:REF][@DATE], e.g. user, literature:Smith2019@2019-03-01. Repeatable.",
)
@click.option("--added-by", "added_by", default=None, help="Discovery stamp (who surfaced this entity).")
def hypothesis_create(
    title: str,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    phase: str,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
    origins: tuple[str, ...],
    added_by: str | None,
) -> None:
    """Create a source-authored hypothesis."""

    sections = list(with_sections)
    if phase == "candidate" and "promotion-criteria" not in sections:
        sections.append("promotion-criteria")

    extra = build_origin_frontmatter(origins, added_by)

    create_typed_entity(
        kind="hypothesis",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(related_refs),
        source_refs=list(source_refs),
        phase=phase,
        with_sections=sections,
        without_sections=list(without_sections),
        no_hints=no_hints,
        extra_frontmatter=extra,
    )


@hypothesis_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def hypothesis_show(ref: str, output_format: str) -> None:
    """Show a source-authored hypothesis."""
    show_typed_entity("hypothesis", ref, output_format)


@hypothesis_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def hypothesis_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored hypotheses."""
    list_typed_entities("hypothesis", status, related, output_format)
