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
from science_tool.field_inventory import field_inventory
from science_tool.graph.store import DEFAULT_GRAPH_PATH, query_neighborhood
from science_tool.output import OUTPUT_FORMATS, emit_query_rows, unwrap_instrument
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


# ☠️ NO `--superseded-by`, and its absence is a decision, not an omission.
#
# `superseded_by` is DERIVED: it is the inversion of the canonical `sci:supersedes` edge, and
# `consolidation._prepare_supersession` reads it off the admitted graph. An author flag for it would
# recreate the second authored spelling this arc exists to delete -- a user could write a RESOLVABLE
# `superseded_by` with no canonical edge behind it, and schema AND the resolution check would both
# report green over a supersession grounded in nothing. Author the EDGE; the inverse is written
# for you.
@entity_group.command("edit")
@click.argument("ref")
@click.option("--title")
@click.option("--status")
@click.option("--verdict", help="Epistemic conclusion (hypothesis): what the evidence SAYS.")
@click.option(
    "--closure-basis",
    help="Why the entity closed: what a person DID. Required by `retired`/`archived`.",
)
# The one lineage field that IS authored. `superseded` is discharged by any of `superseded_by`,
# `resynthesized_into`, or `closure_basis` -- and the first is derived, so without this flag a SPLIT
# supersession would be a state the schema admits and no writer in the toolkit can produce.
@click.option(
    "--resynthesized-into",
    "resynthesized_into",
    multiple=True,
    help="Successor hypothesis this one was split into (repeatable). Must resolve to a live one.",
)
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option("--source-ref", "source_refs", multiple=True, help="Source reference (repeatable)")
@click.option("--updated")
def entity_edit(
    ref: str,
    title: str | None,
    status: str | None,
    verdict: str | None,
    closure_basis: str | None,
    resynthesized_into: tuple[str, ...],
    related_refs: tuple[str, ...],
    source_refs: tuple[str, ...],
    updated: str | None,
) -> None:
    """Edit source-authored entity metadata.

    `--verdict` and `--closure-basis` are accepted ATOMICALLY with the `--status` transition they
    discharge, because a terminal status without its basis is not a write that needs a follow-up --
    it is a write that does not happen.
    """

    try:
        result = edit_entity(
            Path.cwd(),
            ref,
            title=title,
            status=status,
            verdict=verdict,
            closure_basis=closure_basis,
            resynthesized_into=list(resynthesized_into) or None,
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


@entity_group.command("field-inventory")
@click.option("--kind", required=True, help="Entity kind to inventory (e.g. hypothesis).")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_field_inventory(kind: str, output_format: str) -> None:
    """Report every AUTHORED frontmatter key for a kind, with the number of files carrying it.

    Report-only. This is the declare-or-delete instrument: a key absent from this report but
    present on disk becomes a hard validation failure the moment the kind's schema is closed.
    """

    inventory = field_inventory(Path.cwd(), kind)
    rows = [
        {"key": key, "files": count}
        for key, count in sorted(inventory.items(), key=lambda item: (-item[1], item[0]))
    ]
    emit_query_rows(
        output_format=output_format,
        title=f"Authored frontmatter keys — {kind}",
        columns=[("key", "Key"), ("files", "Files")],
        rows=rows,
        meta={"kind": kind, "keys": len(rows)},
    )


@entity_group.command("status-inventory")
@click.option(
    "--adjudication",
    type=click.Path(path_type=Path, exists=True),
    help="Override the canonical .science/hypothesis-lifecycle.adjudication.yaml with another "
    "YAML of explicit author decisions: {entity_id: {status, verdict?, closure_basis?}}.",
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_status_inventory(adjudication: Path | None, output_format: str) -> None:
    """Plan the hypothesis lifecycle/verdict split. Report-only — writes nothing.

    `phase` is the lifecycle; `status` was only ever the verdict (design rev 7). A file whose
    `status` is terminal lost its lifecycle, its verdict AND its closure reason at once, so it is
    REFUSED rather than guessed — and escapes only via an authored adjudication entry.

    The adjudication is read from `.science/hypothesis-lifecycle.adjudication.yaml` — the same
    path the migration consumes, so what discharges a refusal here discharges it there.
    """

    from science_tool.status_inventory import adjudication_for, inventory, load_adjudication

    decisions = (
        load_adjudication(adjudication) if adjudication else adjudication_for(Path.cwd())
    )
    try:
        result = inventory(Path.cwd(), adjudication=decisions)
    except KeyError as exc:
        raise click.ClickException(str(exc).strip('"')) from exc

    rows = [
        {
            "id": row.entity_id,
            "status": row.status or "—",
            "phase": row.phase or "—",
            "target_status": row.target_status or "REFUSED",
            "verdict": row.target_verdict or "—",
            "ambiguity": row.ambiguity or "",
        }
        for row in result.rows
    ]
    emit_query_rows(
        output_format=output_format,
        title="Hypothesis lifecycle / verdict plan",
        columns=[
            ("id", "ID"),
            ("status", "status (old)"),
            ("phase", "phase (old)"),
            ("target_status", "status (new)"),
            ("verdict", "verdict (new)"),
            ("ambiguity", "Refused because"),
        ],
        rows=rows,
        meta={
            "total": len(result.rows),
            "deterministic": len(result.deterministic),
            "refused": len(result.ambiguous),
        },
    )


@entity_group.command("migrate-hypothesis")
@click.option("--apply", "apply_changes", is_flag=True, help="Write. Without this, plan only.")
@click.option(
    "--resume",
    "resume_interrupted",
    is_flag=True,
    help="Finish an INTERRUPTED write pass from its journal. Never re-plans.",
)
@click.option(
    "--preflight-all",
    is_flag=True,
    help="Render and validate every root in --manifest. Writes NOTHING, anywhere.",
)
@click.option(
    "--manifest",
    type=click.Path(path_type=Path, exists=True),
    help="Roster JSON of project roots: [{\"root\": \"~/d/mm30\", ...}, ...] (Task 11 Step 0).",
)
def entity_migrate_hypothesis(
    apply_changes: bool,
    resume_interrupted: bool,
    preflight_all: bool,
    manifest: Path | None,
) -> None:
    """Migrate this project's hypotheses to entity schema 2. Two-phase and ALL-OR-NONE.

    `status` becomes the LIFECYCLE and `verdict` the epistemic conclusion; the eight ruled deletes
    go; `author_stated_evidence` becomes `source_stated_evidence`. Every target is rendered AND
    validated against this project's COMPOSED schema before a single byte is written, and the
    version pin is the final act — so a project is on schema 2 only once its files actually are.

    `--preflight-all` is what makes the slice atomic across REPOSITORIES rather than merely ordered:
    no root is applied until every root's rendered target has passed. Without it the rollout degrades
    to per-root validate-then-write, which leaves the most refutation-capable corpus for last, after
    the others are already written.
    """
    import json as _json

    from science_tool.migrate_hypothesis import MigrationRefused, migrate, resume

    if preflight_all:
        if manifest is None:
            raise click.ClickException("--preflight-all requires --manifest")
        roster = _json.loads(manifest.read_text(encoding="utf-8"))
        failures: list[str] = []
        for entry in roster:
            root = Path(entry["root"]).expanduser()
            try:
                planned = migrate(root, apply=False)
            except MigrationRefused as exc:
                failures.append(f"{root}:\n{exc}")
            else:
                click.echo(f"  ok  {root}  ({len(planned)} hypotheses)")
        if failures:
            raise click.ClickException(
                f"{len(failures)} of {len(roster)} roots FAILED preflight. Nothing was written, in "
                "any root.\n\n" + "\n\n".join(failures)
            )
        click.echo(f"\nAll {len(roster)} roots pass preflight.")
        return

    try:
        paths = resume(Path.cwd()) if resume_interrupted else migrate(Path.cwd(), apply=apply_changes)
    except MigrationRefused as exc:
        raise click.ClickException(str(exc)) from exc

    verb = "migrated" if (apply_changes or resume_interrupted) else "would migrate"
    click.echo(f"{verb} {len(paths)} hypotheses")
    if not (apply_changes or resume_interrupted):
        click.echo("(dry run — nothing written; re-run with --apply)")


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
    rows = unwrap_instrument(
        query_neighborhood(
            graph_path=DEFAULT_GRAPH_PATH,
            center=location.entity_id,
            hops=hops,
            graph_layer="graph/knowledge",
            limit=200,
        ),
        what="entity neighbors",
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
    """Mark an entity as reviewed-as-of today.

    Works on any kind whose curation_scope admits review — epistemic kinds and the
    ratified correspondence kinds (plan, spec, method, ...). A review must record an
    artifact via --note; a bare timestamp bump is rejected to prevent review-theater.
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


@entity_group.command("rotation")
@click.option(
    "--all",
    "show_all",
    is_flag=True,
    default=False,
    help="Show the whole ranked queue, not just this sweep's budget.",
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def entity_rotation(show_all: bool, output_format: str) -> None:
    """Rank the reviewable corpus least-recently-reviewed first, printing this sweep's budget.

    Advisory and stateless: it reviews nothing. Review a listed entity with
    `science entity review <ref> --note ...`. Rotation reaches full coverage in a
    bounded number of sweeps only when each sweep both completes its budget AND stamps
    its reviews with a date strictly later than the corpus's current maximum
    last_reviewed; completing the budget alone does not guarantee coverage.
    """
    from datetime import date

    from science_tool.curate.rotation import RotationError, select_rotation

    try:
        result = select_rotation(Path.cwd(), today=date.today())
    except (EntityCommandError, RotationError) as exc:
        raise click.ClickException(str(exc)) from exc

    shown = result.rows if show_all else result.rows[: result.budget]
    coverage_clause = f" (coverage: {result.coverage_rounds} sweeps)" if result.coverage_rounds else ""
    title = f"rotation — {result.budget} of {result.pool_size}{coverage_clause}"

    def _never(value: object, _row: object) -> str:
        return "never" if value is None else str(value)

    def _selected(value: object, _row: object) -> str:
        return "✓" if value else ""

    emit_query_rows(
        output_format=output_format,
        title=title,
        columns=[
            ("rank", "#"),
            ("id", "ID"),
            ("last_reviewed", "Last reviewed"),
            ("age_days", "Age (days)"),
            ("selected", "Sweep"),
            ("freshness", "Freshness"),
        ],
        rows=shown,
        meta={
            "pool_size": result.pool_size,
            "budget": result.budget,
            "displayed": len(shown),
            "coverage_rounds": result.coverage_rounds,
            "graph_source": result.graph_source,
        },
        renderers={"last_reviewed": _never, "age_days": _never, "selected": _selected},
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
