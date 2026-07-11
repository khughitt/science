"""`science evidence-lines` command group — source-authored evidence-line CRUD."""

from __future__ import annotations

import click

from science_tool.output import OUTPUT_FORMATS
from science_tool.typed_entity_cli import create_typed_entity, list_typed_entities, show_typed_entity


@click.group("evidence-lines")
def evidence_line_group() -> None:
    """Evidence-line source commands."""


@evidence_line_group.command("create")
@click.argument("title")
@click.option("--target", required=True, help="Target proposition or claim reference")
@click.option("--stance", required=True, type=click.Choice(["supports", "disputes"]), help="Evidence stance")
@click.option("--source", default=None, help="Source reference")
@click.option("--strength", default=None, type=click.Choice(["strong", "moderate", "weak"]))
@click.option(
    "--evidence-type",
    default=None,
    type=click.Choice(
        [
            "literature",
            "literature_evidence",
            "empirical_data",
            "empirical_data_evidence",
            "simulation",
            "simulation_evidence",
            "benchmark",
            "benchmark_evidence",
            "expert_judgment",
            "negative_result",
        ]
    ),
)
@click.option("--independence", default=None, type=click.Choice(["independent", "shared-source", "circular"]))
@click.option("--independence-group", default=None, help="Independence group key for shared-source/circular evidence")
@click.option(
    "--belief-eligible/--no-belief-eligible",
    default=None,
    help="Whether the line can contribute to belief aggregation; use --no-belief-eligible for staged lines",
)
@click.option(
    "--dispute-scope",
    default=None,
    type=click.Choice(["whole_claim", "generalization", "mechanism", "boundary"]),
)
@click.option(
    "--evidence-role",
    default=None,
    type=click.Choice(["direct_test", "proxy_support", "background_constraint", "negative_control", "model_criticism"]),
)
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
@click.option("--with", "with_sections", multiple=True, help="Include optional template section key (repeatable)")
@click.option("--without", "without_sections", multiple=True, help="Drop required template section key (repeatable)")
@click.option("--no-hints", is_flag=True, help="Strip authored HTML hint comments from the rendered shell")
def evidence_line_create(
    title: str,
    target: str,
    stance: str,
    source: str | None,
    strength: str | None,
    evidence_type: str | None,
    independence: str | None,
    independence_group: str | None,
    belief_eligible: bool | None,
    dispute_scope: str | None,
    evidence_role: str | None,
    related_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
) -> None:
    """Create a source-authored evidence line."""

    extra_frontmatter: dict[str, object] = {
        "target": target,
        "stance": stance,
    }
    if source:
        extra_frontmatter["source"] = source
        source_refs = [source]
    else:
        source_refs = []
    if strength:
        extra_frontmatter["strength"] = strength
    if evidence_type:
        extra_frontmatter["evidence_type"] = evidence_type
    if independence:
        extra_frontmatter["independence"] = independence
    if independence_group:
        extra_frontmatter["independence_group"] = independence_group
    if belief_eligible is not None:
        extra_frontmatter["belief_eligible"] = belief_eligible
    if dispute_scope:
        extra_frontmatter["dispute_scope"] = dispute_scope
    if evidence_role:
        extra_frontmatter["evidence_role"] = evidence_role

    create_typed_entity(
        kind="evidence-line",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(related_refs),
        source_refs=source_refs,
        with_sections=list(with_sections),
        without_sections=list(without_sections),
        no_hints=no_hints,
        extra_frontmatter=extra_frontmatter,
    )


@evidence_line_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def evidence_line_show(ref: str, output_format: str) -> None:
    """Show a source-authored evidence line."""
    show_typed_entity("evidence-line", ref, output_format)


@evidence_line_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def evidence_line_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored evidence lines."""
    list_typed_entities("evidence-line", status, related, output_format)
