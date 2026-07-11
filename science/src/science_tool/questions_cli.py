"""`science questions` command group — question-file management."""

from __future__ import annotations

from pathlib import Path

import click

from science_tool.output import OUTPUT_FORMATS, emit
from science_tool.typed_entity_cli import (
    build_origin_frontmatter,
    create_typed_entity,
    list_typed_entities,
    show_typed_entity,
)


@click.group("questions")
def question_group() -> None:
    """Question-file management commands."""


@question_group.command("create")
@click.argument("title")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--id", "entity_id")
@click.option("--slug")
@click.option("--status")
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
def question_create(
    title: str,
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    with_sections: tuple[str, ...],
    without_sections: tuple[str, ...],
    no_hints: bool,
    origins: tuple[str, ...],
    added_by: str | None,
) -> None:
    """Create a source-authored question."""

    extra = build_origin_frontmatter(origins, added_by)

    create_typed_entity(
        kind="question",
        title=title,
        entity_id=entity_id,
        slug=slug,
        status=status,
        related=list(related_refs),
        source_refs=list(source_refs),
        with_sections=list(with_sections),
        without_sections=list(without_sections),
        no_hints=no_hints,
        extra_frontmatter=extra,
    )


@question_group.command("show")
@click.argument("ref")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def question_show(ref: str, output_format: str) -> None:
    """Show a source-authored question."""
    show_typed_entity("question", ref, output_format)


@question_group.command("list")
@click.option("--status")
@click.option("--related")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def question_list(status: str | None, related: str | None, output_format: str) -> None:
    """List source-authored questions."""
    list_typed_entities("question", status, related, output_format)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@question_group.command("reserve")
@click.option("--slug", required=True, help="Kebab-case slug for the question (will be normalized)")
@click.option("--title", default=None, help="Question title (used in frontmatter and H1)")
@click.option("--related", default=None, help="Comma-separated related entity IDs")
@click.option("--ontology", default=None, help="Comma-separated ontology terms")
@click.option("--source-refs", default=None, help="Comma-separated source refs, e.g. cite:Smith2024 or paper:Smith2024")
@click.option("--datasets", default=None, help="Comma-separated dataset IDs")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Project root; questions are written under entities/questions/.",
)
@click.option(
    "--questions-dir",
    default=None,
    type=click.Path(path_type=Path),
    help="Deprecated override: write to this directory verbatim instead of <root>/entities/questions.",
)
@click.option(
    "--template",
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Override body template (file content used verbatim, with {title} substituted)",
)
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
    help="Output format. `--json` is kept as a convenience alias.",
)
def question_reserve_cmd(
    slug: str,
    title: str | None,
    related: str | None,
    ontology: str | None,
    source_refs: str | None,
    datasets: str | None,
    project_root: Path,
    questions_dir: Path | None,
    template: Path | None,
    as_json: bool,
    output_format: str,
) -> None:
    """Atomically reserve the next question number and write a stub file.

    Writes ``entities/questions/NNNN-slug.md`` under the project root.
    Designed for parallel subagents: reservation locks on the NUMBER (via a
    per-number sentinel), so concurrent reserves with different slugs never
    collide on a number. Returns the assigned path so the caller can write
    the body without re-querying the directory.
    """
    from science_tool.questions import reserve_question

    template_body = template.read_text(encoding="utf-8") if template else None
    reservation = reserve_question(
        project_root,
        slug,
        title=title,
        related=_split_csv(related),
        ontology_terms=_split_csv(ontology),
        source_refs=_split_csv(source_refs),
        datasets=_split_csv(datasets),
        template_body=template_body,
        questions_dir=questions_dir,
    )

    def _render() -> None:
        click.echo(f"Reserved {reservation.id}")
        click.echo(f"  path: {reservation.path}")

    effective_format = "json" if (as_json or output_format == "json") else output_format
    emit(
        output_format=effective_format,
        payload={
            "id": reservation.id,
            "number": reservation.number,
            "padded": reservation.padded,
            "slug": reservation.slug,
            "path": str(reservation.path),
        },
        render_text=_render,
    )
