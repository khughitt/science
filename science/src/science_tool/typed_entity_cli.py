"""Shared CLI adapters for the typed-entity command groups.

These adapters bridge Click commands (entity/entities and the six per-kind
entity groups: proposition, evidence-line, hypothesis, discussion,
interpretation, question) to the domain-level entity helpers in
`science_tool.entities`. They own CLI concerns — argument validation,
`click.ClickException`/`click.BadParameter` raising, and stdout rendering —
so `entities.py` itself stays free of any `click` dependency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
from pydantic import ValidationError
from rich.text import Text

from science_tool.entities import (
    EntityCommandError,
    create_entity,
    find_entity,
    list_entities,
    parse_origin_spec,
)
from science_tool.output import emit, emit_query_rows
from science_tool.styles import (
    entity_table_renderers,
    get_console,
    render_entity_kind,
    render_entity_ref,
    render_entity_status,
    render_muted,
)


def build_origin_frontmatter(origins: tuple[str, ...], added_by: str | None) -> dict[str, object]:
    """Parse `--origin`/`--added-by` CLI inputs into an `extra_frontmatter` dict.

    Raises `click.BadParameter` (nonzero exit, no file written) on a
    malformed `--origin` spec — validation happens here, before
    `create_entity` performs any write.
    """
    extra: dict[str, object] = {}
    try:
        if origins:
            extra["origins"] = [parse_origin_spec(spec) for spec in origins]
    except ValidationError as exc:
        raise click.BadParameter(f"invalid --origin: {exc}") from exc
    if added_by:
        extra["added_by"] = added_by
    return extra


def create_typed_entity(
    *,
    kind: str,
    title: str,
    entity_id: str | None,
    slug: str | None,
    status: str | None,
    related: list[str],
    source_refs: list[str],
    phase: str | None = None,
    with_sections: list[str] | None = None,
    without_sections: list[str] | None = None,
    no_hints: bool = False,
    extra_frontmatter: dict[str, object] | None = None,
) -> None:
    try:
        result = create_entity(
            project_root=Path.cwd(),
            kind=kind,
            title=title,
            entity_id=entity_id,
            slug=slug,
            status=status,
            related=related,
            source_refs=source_refs,
            phase=phase,
            with_sections=with_sections,
            without_sections=without_sections,
            no_hints=no_hints,
            extra_frontmatter=extra_frontmatter,
        )
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Created {result.entity_id} at {result.path.relative_to(Path.cwd())}")
    emit_entity_warnings(result.warnings)


def show_typed_entity(kind: str, ref: str, output_format: str) -> None:
    try:
        location = find_entity(Path.cwd(), ref)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    if location.kind != kind:
        raise click.ClickException(f"Expected {kind} entity, got {location.entity_id}")
    emit_entity_show(location, output_format)


def list_typed_entities(kind: str, status: str | None, related: str | None, output_format: str) -> None:
    try:
        rows = list_entities(Path.cwd(), kind=kind, status=status, related=related)
    except EntityCommandError as exc:
        raise click.ClickException(str(exc)) from exc
    emit_query_rows(
        output_format=output_format,
        title=ENTITY_LIST_TITLES.get(kind, kind.replace("-", " ").title() + "s"),
        columns=[("id", "ID"), ("status", "Status"), ("title", "Title"), ("path", "Path")],
        rows=rows,
        renderers=entity_table_renderers(),
    )


ENTITY_LIST_TITLES = {
    "discussion": "Discussions",
    "evidence-line": "Evidence Lines",
    "hypothesis": "Hypotheses",
    "interpretation": "Interpretations",
    "proposition": "Propositions",
    "question": "Questions",
}


def _entity_show_payload(location: Any) -> dict[str, object]:
    return {
        "id": location.entity_id,
        "kind": location.kind,
        "title": location.title,
        "status": location.status,
        "path": location.rel_path,
        "related": _frontmatter_string_list(location.frontmatter.get("related")),
        "source_refs": _frontmatter_string_list(location.frontmatter.get("source_refs")),
        "body": location.body,
    }


def emit_entity_show(location: Any, output_format: str) -> None:
    payload = _entity_show_payload(location)

    def _render() -> None:
        console = get_console(file=click.get_text_stream("stdout"))
        _print_entity_field(console, "id", render_entity_ref(str(payload["id"])))
        _print_entity_field(console, "type", render_entity_kind(str(payload["kind"])))
        _print_entity_field(console, "title", Text(str(payload["title"])))
        _print_entity_field(console, "status", render_entity_status(str(payload["status"])))
        _print_entity_field(console, "path", render_muted(payload["path"]))
        _print_entity_refs_field(console, "related", payload["related"])
        _print_entity_refs_field(console, "source_refs", payload["source_refs"])
        if location.body:
            click.echo()
            console.print(Text(location.body.rstrip("\n")))

    emit(output_format=output_format, payload=payload, render_text=_render, sort_keys=True)


def _print_entity_field(console: Any, label: str, value: Text) -> None:
    line = Text(f"{label}: ")
    line.append_text(value)
    console.print(line)


def _print_entity_refs_field(console: Any, label: str, refs: object) -> None:
    line = Text(f"{label}: ")
    if isinstance(refs, list):
        for index, ref in enumerate(refs):
            if index:
                line.append(", ")
            line.append_text(render_entity_ref(str(ref)))
    console.print(line)


def emit_entity_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        click.echo(f"WARNING: {warning}")


def _frontmatter_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
