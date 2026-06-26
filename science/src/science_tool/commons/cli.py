"""Click CLI for `science commons`."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
import yaml

from science_tool.commons.adapter import CommonsEntityAdapter, CommonsEntityRecord
from science_tool.commons.bootstrap import init_commons
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import (
    CommonsError,
    CommonsRootNotFoundError,
    PromoteInputError,
    PromoteWriteError,
)
from science_tool.commons.inventory import build_commons_inventory
from science_tool.commons.overlay import (
    MergedEntity,
    resolve_entity,
    validate_project_overlays,
)
from science_tool.commons.promote import (
    PROMOTE_KIND_DATASET,
    PROMOTE_KIND_PAPER,
    PROMOTE_KIND_THEME,
    PROMOTE_KIND_TOPIC,
    DiscoveryResult,
    PromoteDecision,
    PromoteKindConfig,
    PromotePlan,
    _validate_mixin_stacking,
    apply_promote,
    discover_candidates,
    plan_promote,
)
from science_tool.commons.query import CommonsQuery
from science_tool.commons.registry import RegistryBuilder
from science_tool.commons.resolver import resolve
from science_tool.commons.validator import CommonsValidator
from science_tool.output import OUTPUT_FORMATS, emit_query_rows
from science_tool.styles import entity_table_renderers

if TYPE_CHECKING:
    from science_model.entity_schema.profile import ProfileComponent


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
            click.echo(json.dumps(_record_to_json(record, root), indent=2, sort_keys=True))
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


@commons_group.command("list")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
def list_cmd(output_format: str) -> None:
    """List all indexed commons entities."""
    root = _require_root()
    try:
        records = CommonsQuery(root).list()
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    rows = [_record_summary(record, root) for record in records]
    emit_query_rows(
        output_format=output_format,
        title="Commons",
        columns=[
            ("id", "ID"),
            ("kind", "Kind"),
            ("status", "Status"),
            ("title", "Title"),
            ("path", "Path"),
        ],
        rows=rows,
        renderers=entity_table_renderers(),
    )


@commons_group.command("find")
@click.argument("entity_type", type=click.Choice(["dataset", "paper", "topic", "theme"]))
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
                str(record.datapackage_path.relative_to(root)) if record.datapackage_path is not None else None
            ),
            "mtime_ns": record.mtime_ns,
        },
    }


def _record_summary(record: CommonsEntityRecord, root: Path) -> dict[str, str]:
    return {
        "id": record.canonical_id,
        "kind": record.type,
        "status": str(record.frontmatter.get("status", "")),
        "title": str(record.frontmatter.get("title", "")),
        "path": str(record.body_path.relative_to(root)),
    }


def _merged_to_json(merged: MergedEntity) -> dict:
    overlay = merged.overlay
    overlay_json = None
    if overlay is not None:
        overlay_json = {
            "project": overlay.project,
            "overlay_path": str(overlay.overlay_path.relative_to(overlay.project_root)),
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
            field for field, src in merged.field_sources.items() if src in ("overlay", "canonical+overlay")
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
            raise click.UsageError("--project cannot be combined with --type/--slug")
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
    report = CommonsValidator(CommonsEntityAdapter(root)).validate(type=entity_type, slug=slug)
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


@commons_group.command("inventory")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the payload to FILE instead of stdout.",
)
def inventory_cmd(output: Path | None) -> None:
    """Emit the inventory_v2 payload for the whole commons store."""
    try:
        payload = build_commons_inventory()
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc
    rendered = payload.model_dump_json(indent=2) + "\n"
    if output is None:
        click.echo(rendered, nl=False)
    else:
        output.write_text(rendered, encoding="utf-8")


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


@commons_group.group("promote")
def promote_group() -> None:
    """Promote per-project entities into the shared commons store."""


def _parse_version_tuple(version: str) -> tuple[int, ...]:
    """Parse a dot-separated integer version into a tuple of ints.

    Rejects anything that isn't dot-separated non-negative integers.
    Raises PromoteMixinResolutionError on a bad shape.
    """
    from science_tool.commons.errors import PromoteMixinResolutionError

    parts = version.split(".")
    try:
        nums = tuple(int(p) for p in parts)
    except ValueError as exc:
        raise PromoteMixinResolutionError(
            f"version {version!r}: expected dot-separated integers (e.g. '1.0')."
        ) from exc
    if not nums or any(n < 0 for n in nums):
        raise PromoteMixinResolutionError(
            f"version {version!r}: expected dot-separated non-negative integers."
        )
    return nums


def _resolve_mixin_arg(raw: str) -> "ProfileComponent":
    """Parse one --mixin argument into a ProfileComponent.

    Accepts either:
      - Explicit: 'bio.matrix/1.0' -> ProfileComponent('bio.matrix', '1.0')
      - Sugar: 'bio.matrix' -> resolved to the highest installed version
        by scanning extension-bio-matrix-*.json under the schemas package.

    The name MUST start with 'bio.' and have a non-empty suffix; this
    prevents --mixin from being abused to stack base or type-mixin
    schemas (e.g. dataset/1.0). The version MUST be a dot-separated
    integer tuple.

    Raises PromoteMixinResolutionError on malformed input or a sugar
    form with no installed schema.
    """
    from importlib import resources

    from science_model.entity_schema.profile import ProfileComponent

    from science_tool.commons.errors import PromoteMixinResolutionError

    raw = raw.strip()
    if not raw:
        raise PromoteMixinResolutionError("--mixin '': empty argument")

    if "/" in raw:
        name, _, version = raw.partition("/")
        if not name or not version:
            raise PromoteMixinResolutionError(
                f"--mixin {raw!r}: expected '<name>/<version>' "
                "(e.g. 'bio.matrix/1.0')."
            )
    else:
        name, version = raw, None

    if not name.startswith("bio.") or len(name) <= len("bio."):
        raise PromoteMixinResolutionError(
            f"--mixin {raw!r}: name must start with 'bio.' and have a "
            "non-empty suffix (e.g. 'bio.matrix'). Use --mixin only for "
            "bio extensions; base and type mixins are auto-included."
        )

    if version is not None:
        _parse_version_tuple(version)
        return ProfileComponent(name=name, version=version)

    flat = name.replace(".", "-")
    prefix = f"extension-{flat}-"
    candidates: list[tuple[tuple[int, ...], str]] = []
    for r in resources.files("science_model.schemas").iterdir():
        rname = r.name
        if rname.startswith(prefix) and rname.endswith(".json"):
            version_str = rname[len(prefix) : -len(".json")]
            try:
                nums = _parse_version_tuple(version_str)
            except PromoteMixinResolutionError:
                continue  # ignore weirdly-named files on disk
            candidates.append((nums, version_str))
    if not candidates:
        raise PromoteMixinResolutionError(
            f"--mixin {raw!r}: no installed extension-{flat}-*.json schema. "
            "Known bio extensions: bio.matrix, bio.table, bio.rnaseq, "
            "bio.scrna, bio.cna."
        )
    highest_version = max(candidates)[1]
    return ProfileComponent(name=name, version=highest_version)


def _promote_from_options(kind: PromoteKindConfig) -> list[click.Parameter]:
    return [
        click.Argument(["entity_id"], required=False, default=None),
        click.Option(
            ["--from", "from_"],
            multiple=True,
            required=True,
            metavar="SLUG",
            help="Registered project id (NOT name). Required; repeatable for bulk + dedup.",
        ),
        click.Option(["--apply", "apply_flag"], is_flag=True, default=False, help="Write changes (default: dry-run)."),
        click.Option(
            ["--limit"],
            type=int,
            default=None,
            help=f"Bulk only: stop after N {kind.commons_subdir} (slug-sorted).",
        ),
    ]


@promote_group.command("paper", params=_promote_from_options(PROMOTE_KIND_PAPER))
def promote_paper_cmd(
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_flag: bool,
    limit: int | None,
) -> None:
    """Promote paper entities into the commons store.

    Dry-run is the default; pass --apply to write. Conflicts on canonical fields
    prompt interactively in BOTH dry-run and apply (so dry-run is a faithful
    preview). Use --limit 0 to get a discovery-only summary without prompts.
    """
    _promote_kind_cmd(
        kind=PROMOTE_KIND_PAPER,
        entity_id=entity_id,
        from_=from_,
        apply_=apply_flag,
        limit=limit,
    )


@promote_group.command("topic", params=_promote_from_options(PROMOTE_KIND_TOPIC))
def promote_topic_cmd(
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_flag: bool,
    limit: int | None,
) -> None:
    """Promote topic entities into the commons store."""
    _promote_kind_cmd(
        kind=PROMOTE_KIND_TOPIC,
        entity_id=entity_id,
        from_=from_,
        apply_=apply_flag,
        limit=limit,
    )


@promote_group.command("theme", params=_promote_from_options(PROMOTE_KIND_THEME))
def promote_theme_cmd(
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_flag: bool,
    limit: int | None,
) -> None:
    """Promote theme entities into the commons store."""
    _promote_kind_cmd(
        kind=PROMOTE_KIND_THEME,
        entity_id=entity_id,
        from_=from_,
        apply_=apply_flag,
        limit=limit,
    )


@promote_group.command(
    "dataset",
    params=_promote_from_options(PROMOTE_KIND_DATASET)
    + [
        click.Option(
            ["--slug"],
            required=True,
            help="Dataset slug to promote (required in v1; batch deferred to v1.1).",
        ),
        click.Option(
            ["--mixin", "mixin_args"],
            multiple=True,
            default=(),
            help=(
                "Bio extension to apply to the promoted dataset; repeatable. "
                "Use explicit form (bio.matrix/1.0) or sugar form (bio.rnaseq). "
                "At most one structural extension (bio.matrix or bio.table) and "
                "one domain extension (bio.rnaseq, bio.scrna, or bio.cna) may be "
                "stacked; choose extensions that match the dataset modality."
            ),
        ),
        click.Option(
            ["--verify-digests"],
            "verify_digests",
            is_flag=True,
            default=False,
            help=(
                "Re-verify each sourced resource's build-stamped digest against "
                "its local bytes (when resolvable on this host). Off by default: "
                "promote trusts the stamped digest and does no byte I/O."
            ),
        ),
    ],
)
def promote_dataset_cmd(
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_flag: bool,
    limit: int | None,
    slug: str,
    mixin_args: tuple[str, ...],
    verify_digests: bool,
) -> None:
    """Promote one dataset entity into the commons store."""
    if entity_id is not None:
        raise click.UsageError("dataset promotion uses --slug; do not pass a positional <entity_id>")

    try:
        mixin_extensions = tuple(_resolve_mixin_arg(m) for m in mixin_args)
        _validate_mixin_stacking(mixin_extensions)
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc

    _promote_kind_cmd(
        kind=PROMOTE_KIND_DATASET,
        entity_id=f"dataset:{slug}",
        from_=from_,
        apply_=apply_flag,
        limit=limit,
        mixin_extensions=mixin_extensions,
        verify_digests=verify_digests,
    )


def _promote_kind_cmd(
    *,
    kind: PromoteKindConfig,
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_: bool,
    limit: int | None,
    mixin_extensions: tuple["ProfileComponent", ...] = (),
    verify_digests: bool = False,
) -> None:
    """Shared implementation for `commons promote <kind>` commands."""
    root = resolve_commons_root()
    if not root.exists():
        raise click.ClickException(f"commons store missing at {root}; run `science commons init` first")

    if entity_id is not None and len(from_) != 1:
        raise click.ClickException(f"single-entity form (`promote {kind.kind} <id>`) requires exactly one --from")
    if limit is not None and entity_id is not None:
        raise click.UsageError("--limit applies to bulk form only; cannot combine with <entity_id>")

    try:
        discovery = discover_candidates(list(from_), kind)
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc

    if entity_id is not None:
        if not entity_id.startswith(kind.id_prefix):
            raise click.ClickException(f"expected `{kind.id_prefix}<slug>`, got {entity_id!r}")
        wanted = entity_id.removeprefix(kind.id_prefix)
        if kind.slug_match == "casefold":
            wanted = wanted.casefold()
        filtered = {k: v for k, v in discovery.candidates_by_slug.items() if k == wanted}
        discovery = DiscoveryResult(
            candidates_by_slug=filtered,
            failed_candidates=[
                f
                for f in discovery.failed_candidates
                if _failed_candidate_matches_slug(f, wanted=wanted, kind=kind)
            ],
        )

    # `--limit 0` is a discovery-only summary (per command help): report the
    # FULL discovered count, then stop before planning (which can prompt on
    # conflicts). `--limit N` (N>0) caps the bulk set to the first N slug
    # groups. The count below must be taken from the un-truncated discovery for
    # the limit==0 case, so the summary is accurate rather than always "0".
    discovery_only = limit == 0
    if limit is not None and limit > 0:
        sorted_keys = sorted(discovery.candidates_by_slug)[:limit]
        truncated = {k: discovery.candidates_by_slug[k] for k in sorted_keys}
        discovery = DiscoveryResult(
            candidates_by_slug=truncated,
            failed_candidates=discovery.failed_candidates,
        )

    n_total = sum(len(v) for v in discovery.candidates_by_slug.values())
    n_groups = len(discovery.candidates_by_slug)
    n_multi = sum(1 for v in discovery.candidates_by_slug.values() if len(v) > 1)
    n_single = n_groups - n_multi
    click.echo(
        f"Discovered {n_total} {kind.kind} candidates across {len(from_)} projects "
        f"({n_groups} unique slugs, {n_single} single-instance, "
        f"{n_multi} multi-instance)."
    )
    if discovery.failed_candidates:
        click.echo(f"  • {len(discovery.failed_candidates)} failed candidates:")
        for f in discovery.failed_candidates[:5]:
            click.echo(f"    - {f.source_path}: {f.error_message}")
        if len(discovery.failed_candidates) > 5:
            click.echo(f"    … and {len(discovery.failed_candidates) - 5} more")

    if discovery_only:
        click.echo("Discovery-only summary (--limit 0); re-run without --limit 0 to plan and promote.")
        return

    if not discovery.candidates_by_slug:
        click.echo("Nothing to promote.")
        return

    # Non-interactive runs (piped/redirected stdin) cannot answer a conflict
    # prompt, so a citekey colliding with a different existing entity would abort
    # the whole batch on the first collision. Skip-and-continue instead, and
    # report the skips afterward (fb-2026-05-30-009).
    non_interactive = not sys.stdin.isatty()
    try:
        plan = plan_promote(
            discovery,
            commons_root=root,
            kind=kind,
            from_order=list(from_),
            mixin_extensions=mixin_extensions,
            verify_digests=verify_digests,
            skip_on_conflict=non_interactive,
            skip_on_invalid=non_interactive,
        )
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc

    skipped_on_conflict = [
        fc for fc in plan.failed_candidates if fc.error_class == "PromoteConflictSkipped"
    ]
    if skipped_on_conflict:
        click.echo(
            f"Skipped {len(skipped_on_conflict)} candidate(s) on conflict (non-interactive); "
            "re-run interactively to resolve, or promote under a disambiguated key:",
            err=True,
        )
        for fc in skipped_on_conflict:
            click.echo(f"  - {fc.slug or '?'} (from {fc.project_slug})", err=True)

    skipped_on_invalid = [
        fc for fc in plan.failed_candidates if fc.error_class == "PromoteValidationSkipped"
    ]
    if skipped_on_invalid:
        click.echo(
            f"Skipped {len(skipped_on_invalid)} schema-invalid candidate(s) (non-interactive); "
            "fix the source entity and re-run to promote it:",
            err=True,
        )
        for fc in skipped_on_invalid:
            click.echo(f"  - {fc.slug or '?'} (from {fc.project_slug}): {fc.error_message}", err=True)

    click.echo(
        f"Plan: {len(plan.decisions)} canonical entities, "
        f"{sum(len(d.overlays) for d in plan.decisions)} overlay rewrites."
    )
    for d in plan.decisions:
        renames = [(slug, ov) for slug, ov in d.overlays.items() if ov.rename_from is not None]
        rename_note = f" (rename: {', '.join(slug for slug, _ in renames)})" if renames else ""
        click.echo(f"  {d.slug}{rename_note}")
        for slug, ov in renames:
            rename_from = ov.rename_from
            if rename_from is None:
                continue
            click.echo(f"    rename in {slug}: {rename_from.name} → {ov.path.name}")
        if kind.kind == "dataset":
            _echo_dataset_plan_details(plan, d)

    if not apply_:
        click.echo("Re-run with --apply to execute.")
        return

    try:
        result = apply_promote(plan, commons_root=root, invocation=_invocation())
    except (PromoteInputError, PromoteWriteError) as exc:
        audit_yaml = getattr(exc, "failure_audit_yaml", None)
        if audit_yaml:
            click.echo(
                "Failure-path audit log could not be written. Would-have-been content:\n" + audit_yaml,
                err=True,
            )
        raise click.ClickException(str(exc)) from exc

    click.echo(
        f"Applied op {result.op_id}: commit {result.commons_commit}, "
        f"{len(result.tags_created)} tags, audit log at {result.audit_log_path}"
    )
    # t063 fb-002: rebuild registry.sqlite after a successful apply so the next
    # overlay→commons resolution is not stale. registry.sqlite is gitignored, so
    # this never dirties the working tree.
    rebuild_report = RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    click.echo(f"Reindexed commons registry: {rebuild_report.entities_indexed} entities.")


def _echo_dataset_plan_details(plan: PromotePlan, decision: PromoteDecision) -> None:
    extras = plan.dataset_audit_extras.get(decision.slug, {})
    for artifact in decision.canonical_artifacts:
        click.echo(f"    artifact: {artifact.path}")

    per_resource = extras.get("per_resource", {})
    if isinstance(per_resource, dict) and per_resource:
        click.echo("    resources:")
        for name, hash_and_bytes in sorted(per_resource.items()):
            if (
                isinstance(hash_and_bytes, tuple)
                and len(hash_and_bytes) == 2
                and isinstance(hash_and_bytes[0], str)
            ):
                digest, byte_count = hash_and_bytes
                click.echo(f"      - {name}: {digest}, bytes: {byte_count}")

    override_path = extras.get("override_path")
    if override_path is not None:
        click.echo(f"    data.yaml override: {decision.slug}: {override_path}")

    dropped_fields = extras.get("dropped_fields", [])
    if isinstance(dropped_fields, list | tuple | set) and dropped_fields:
        click.echo("    dropped fields: " + ", ".join(str(field) for field in dropped_fields))
    else:
        click.echo("    dropped fields: (none)")

    verifications = plan.resource_verifications.get(decision.slug, ())
    if verifications:
        click.echo("    verify:")
        for v in verifications:
            click.echo(f"      - [{v.project_slug}] {v.name}: {v.status} ({v.detail})")

    for project_slug, overlay in sorted(decision.overlays.items()):
        click.echo(f"    overlay rewrite: {project_slug}: {overlay.path}")
        overlay_fm = _rendered_frontmatter(overlay.after_content)
        source = overlay_fm.get("source")
        if isinstance(source, str):
            click.echo(f"      source: {source}")


def _failed_candidate_matches_slug(
    failed_candidate: Any,
    *,
    wanted: str,
    kind: PromoteKindConfig,
) -> bool:
    """Return whether a discovery failure belongs to a single-entity request."""
    for raw_slug in (failed_candidate.slug, failed_candidate.source_path.stem):
        if not isinstance(raw_slug, str):
            continue
        normalized = _slug_match_key(raw_slug, kind)
        if normalized == wanted:
            return True
    return False


def _slug_match_key(raw_slug: str, kind: PromoteKindConfig) -> str | None:
    slug = raw_slug.strip()
    if not slug or not kind.slug_regex.match(slug):
        return None
    if kind.slug_match == "casefold":
        return slug.casefold()
    return slug


def _rendered_frontmatter(rendered: str) -> dict[str, Any]:
    if not rendered.startswith("---\n"):
        return {}
    try:
        frontmatter = rendered.split("---\n", 2)[1]
    except IndexError:
        return {}
    parsed = yaml.safe_load(frontmatter)
    return parsed if isinstance(parsed, dict) else {}


def _invocation() -> str:
    """Reconstruct an invocation string from sys.argv for audit logging."""
    import sys

    return " ".join(sys.argv)
