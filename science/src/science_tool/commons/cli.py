"""Click CLI for `science commons`."""

from __future__ import annotations

import json
from pathlib import Path

import click

from science_tool.commons.adapter import CommonsEntityAdapter, CommonsEntityRecord
from science_tool.commons.bootstrap import init_commons
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError, CommonsRootNotFoundError
from science_tool.commons.overlay import (
    MergedEntity,
    resolve_entity,
    validate_project_overlays,
)
from science_tool.commons.query import CommonsQuery
from science_tool.commons.registry import RegistryBuilder
from science_tool.commons.resolver import resolve
from science_tool.commons.validator import CommonsValidator


@click.group("commons")
def commons_group() -> None:
    """Manage the shared knowledge store."""


@commons_group.command("init")
@click.option("--force", is_flag=True, help="Initialize even if the path is non-empty.")
def init_cmd(force: bool) -> None:
    """Create or verify the commons store layout."""
    root = resolve_commons_root()
    try:
        init_commons(root, force=force)
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"commons initialized at {root}")


@commons_group.group("index")
def index_group() -> None:
    """Manage the commons registry index."""


@index_group.command("rebuild")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON report.")
def index_rebuild_cmd(as_json: bool) -> None:
    """Rebuild registry.sqlite from filesystem state."""
    root = _require_root()
    adapter = CommonsEntityAdapter(root)
    report = RegistryBuilder(root, adapter).rebuild()
    if as_json:
        payload = {
            "entities_indexed": report.entities_indexed,
            "errors": [
                {
                    "path": str(e.path),
                    "canonical_id": e.canonical_id,
                    "message": str(e.cause),
                }
                for e in report.errors
            ],
            "duration_ms": report.duration_ms,
        }
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        click.echo(f"indexed {report.entities_indexed} entities in {report.duration_ms} ms")
        for err in report.errors:
            click.echo(f"  error: {err}", err=True)
    if report.errors:
        raise click.exceptions.Exit(1)


def _require_root() -> Path:
    """Resolve the commons root, raising a ClickException if it is missing."""
    root = resolve_commons_root()
    if not root.is_dir():
        exc = CommonsRootNotFoundError(root)
        raise click.ClickException(str(exc)) from exc
    return root


@commons_group.command("show")
@click.argument("entity_id")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.option(
    "--project",
    default=None,
    help="Merge the named registered project's overlay into the entity.",
)
def show_cmd(entity_id: str, as_json: bool, project: str | None) -> None:
    """Print one entity by canonical id, optionally merged with a project overlay."""
    if project is None:
        root = _require_root()
        try:
            record = CommonsQuery(root).show(entity_id)
        except CommonsError as exc:
            raise click.ClickException(str(exc)) from exc
        if as_json:
            click.echo(
                json.dumps(_record_to_json(record, root), indent=2, sort_keys=True)
            )
        else:
            _print_record_human(record)
        return

    try:
        merged = resolve_entity(entity_id, project=project)
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    if merged.overlay is not None and merged.overlay.pin_version:
        click.echo(
            f"warning: pin_version {merged.overlay.pin_version} on overlay is "
            f"inactive until Phase E; merged from live entity",
            err=True,
        )
    if as_json:
        click.echo(json.dumps(_merged_to_json(merged), indent=2, sort_keys=True))
    else:
        _print_merged_human(merged)


@commons_group.command("find")
@click.argument(
    "entity_type", type=click.Choice(["dataset", "paper", "topic", "theme"])
)
@click.option("--tag", "tags", multiple=True, help="Filter by tag (repeatable; AND).")
@click.option(
    "--ontology",
    "ontology_terms",
    multiple=True,
    help="Filter by ontology term (repeatable; AND).",
)
@click.option("--year-from", type=int, default=None, help="(paper only) Inclusive lower bound.")
@click.option("--year-to", type=int, default=None, help="(paper only) Inclusive upper bound.")
@click.option("--slug-glob", default=None, help="fnmatch pattern over slug.")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def find_cmd(
    entity_type: str,
    tags: tuple[str, ...],
    ontology_terms: tuple[str, ...],
    year_from: int | None,
    year_to: int | None,
    slug_glob: str | None,
    as_json: bool,
) -> None:
    """Filter the commons registry."""
    root = _require_root()
    try:
        records = CommonsQuery(root).find(
            entity_type,
            tags=tags,
            ontology_terms=ontology_terms,
            year_from=year_from,
            year_to=year_to,
            slug_glob=slug_glob,
        )
    except ValueError as exc:
        # Bad flag combination (e.g. --year-from on a non-paper type) is a
        # usage error — click.UsageError exits 2.
        raise click.UsageError(str(exc)) from exc
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        click.echo(
            json.dumps(
                [_record_to_json(r, root) for r in records],
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for record in records:
            title = record.frontmatter.get("title", "")
            click.echo(f"{record.canonical_id}\t{title}")


def _record_to_json(record: CommonsEntityRecord, root: Path) -> dict:
    return {
        "canonical_id": record.canonical_id,
        "type": record.type,
        "slug": record.slug,
        "schema_profile": record.schema_profile,
        "frontmatter": record.frontmatter,
        "commons_metadata": {
            "body_path": str(record.body_path.relative_to(root)),
            "datapackage_path": (
                str(record.datapackage_path.relative_to(root))
                if record.datapackage_path is not None
                else None
            ),
            "mtime_ns": record.mtime_ns,
        },
    }


def _merged_to_json(merged: MergedEntity) -> dict:
    overlay = merged.overlay
    overlay_json = None
    if overlay is not None:
        overlay_json = {
            "project": overlay.project,
            "overlay_path": str(
                overlay.overlay_path.relative_to(overlay.project_root)
            ),
            "pin_version": overlay.pin_version,
            "pin_effective_version": overlay.pin_effective_version,
        }
    return {
        "canonical_id": merged.canonical.canonical_id,
        "type": merged.canonical.type,
        "schema_profile": merged.canonical.schema_profile,
        "merged_frontmatter": merged.merged_frontmatter,
        "merged_body": merged.merged_body,
        "field_sources": merged.field_sources,
        "overlay": overlay_json,
    }


def _print_record_human(record: CommonsEntityRecord) -> None:
    click.echo(f"{record.canonical_id}")
    click.echo(f"  title:          {record.frontmatter.get('title', '')}")
    click.echo(f"  schema_profile: {record.schema_profile}")
    tags = record.frontmatter.get("tags") or []
    if tags:
        click.echo(f"  tags:           {', '.join(tags)}")
    terms = record.frontmatter.get("ontology_terms") or []
    if terms:
        click.echo(f"  ontology_terms: {', '.join(terms)}")
    if record.type == "paper":
        authors = record.frontmatter.get("authors") or []
        click.echo(f"  authors:        {', '.join(authors)}")
        click.echo(f"  year:           {record.frontmatter.get('year', '')}")


def _print_merged_human(merged: MergedEntity) -> None:
    record = merged.canonical
    click.echo(f"{record.canonical_id}")
    click.echo(f"  title:          {merged.merged_frontmatter.get('title', '')}")
    click.echo(f"  schema_profile: {record.schema_profile}")
    tags = merged.merged_frontmatter.get("tags") or []
    if tags:
        click.echo(f"  tags:           {', '.join(tags)}")
    if merged.overlay is not None:
        contributed = sorted(
            field
            for field, src in merged.field_sources.items()
            if src in ("overlay", "canonical+overlay")
        )
        click.echo(f"  overlay:        {merged.overlay.project}")
        click.echo(f"    contributed:  {', '.join(contributed)}")
    click.echo("")
    click.echo(merged.merged_body)


@commons_group.command("validate")
@click.option("--type", "entity_type", default=None, help="Filter to one type.")
@click.option("--slug", default=None, help="Filter to one slug.")
@click.option(
    "--project",
    default=None,
    help="Validate every overlay file in the named registered project.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def validate_cmd(
    entity_type: str | None,
    slug: str | None,
    project: str | None,
    as_json: bool,
) -> None:
    """Validate commons entities, or a project's overlay files with --project."""
    if project is not None:
        if entity_type is not None or slug is not None:
            raise click.UsageError(
                "--project cannot be combined with --type/--slug"
            )
        try:
            overlay_report = validate_project_overlays(project)
        except CommonsError as exc:
            raise click.ClickException(str(exc)) from exc
        if as_json:
            click.echo(
                json.dumps(
                    {
                        "checked": overlay_report.checked,
                        "errors": [
                            {
                                "overlay_path": str(e.overlay_path),
                                "canonical_id": e.canonical_id,
                                "message": str(e.cause),
                            }
                            for e in overlay_report.errors
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            click.echo(f"checked {overlay_report.checked} overlays")
            for err in overlay_report.errors:
                click.echo(f"  error: {err}", err=True)
        if overlay_report.errors:
            raise click.exceptions.Exit(1)
        return

    root = _require_root()
    report = CommonsValidator(CommonsEntityAdapter(root)).validate(
        type=entity_type, slug=slug
    )
    if as_json:
        payload = {
            "checked": report.checked,
            "errors": [
                {
                    "path": str(e.path),
                    "canonical_id": e.canonical_id,
                    "message": str(e.cause),
                }
                for e in report.errors
            ],
        }
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        click.echo(f"checked {report.checked} entities")
        for err in report.errors:
            click.echo(f"  error: {err}", err=True)
    if report.errors:
        raise click.exceptions.Exit(1)


@commons_group.group("data")
def data_group() -> None:
    """Resolve bulk data for commons datasets."""


@data_group.command("resolve")
@click.argument("dataset_id")
@click.argument("logical_path")
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
def data_resolve_cmd(dataset_id: str, logical_path: str, as_json: bool) -> None:
    """Resolve DATASET_ID + LOGICAL_PATH to a verified absolute filesystem path."""
    try:
        resolved = resolve(dataset_id, logical_path)
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    if as_json:
        click.echo(
            json.dumps(
                {
                    "dataset_id": resolved.dataset_id,
                    "logical_path": resolved.logical_path,
                    "resolved_path": str(resolved.path),
                    "hash": resolved.hash,
                    "source": resolved.source,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        click.echo(str(resolved.path))
