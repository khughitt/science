"""Collect commons references needed by graph builds.

Graph loading can depend on Science Commons entries, but commons loading
must remain independent of project graph materialization. This module keeps
that dependency one-way by extracting referenced commons IDs from already
loaded project graph sources without performing I/O or commons access.
"""

from __future__ import annotations

from pathlib import Path

from science_model.entities import Entity
from science_model.entity_schema import parse_profile, read_merge_policy
from science_model.ontologies.schema import OntologyCatalog
from science_model.source_contracts import BindingSource
from science_model.source_ref import SourceRef

from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsRootNotFoundError,
    OverlayValidationError,
)
from science_tool.commons.geneset import GenesetCollectionError, parse_geneset_rows
from science_tool.commons.geneset_resources import geneset_resource_frontmatter, read_member_rows
from science_tool.commons.overlay import MergedEntity, OverlayAdapter, merge_entity, validate_overlay_pin
from science_tool.commons.query import CommonsQuery
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import (
    SourceRelation,
    _enrich_raw,
    _normalize_kind,
    is_external_reference,
    is_metadata_reference,
)

_COMMONS_TYPES = frozenset({"dataset", "paper", "topic", "theme"})
_TYPE_TO_DIR = {"dataset": "datasets", "paper": "papers", "topic": "topics", "theme": "themes"}
_OVERLAY_ONLY_FIELDS = (
    "relevance",
    "hypothesis_links",
    "task_links",
    "question_links",
    "project_tags",
    "project_notes",
    "source",
)
_AUDITED_LIST_FIELDS = (
    "related",
    "commits_to",
    "blocked_by",
    "source_refs",
    "evidence_refs",
    "chain",
    "proposition_refs",
    "same_as",
)
_MATERIALIZED_LIST_FIELDS = ("participants", "propositions")


def _load_commons_referenced_entities(
    *,
    project_root: Path,
    project_slug: str,
    project_entities: list[Entity],
    project_relations: list[SourceRelation],
    project_bindings: list[BindingSource],
    identity_table: dict[str, SourceRef],
    registry: EntityRegistry,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> tuple[list[tuple[Entity, SourceRef]], dict[str, str], list[tuple[str, SourceRef]]]:
    overlays = {}
    if (project_root / "overlays").exists():
        for item in OverlayAdapter(project_root, project_slug).scan():
            if isinstance(item, OverlayValidationError):
                raise item
            overlays[item.canonical_id] = item

    referenced_ids = collect_referenced_commons_ids(
        project_root=project_root,
        project_entities=project_entities,
        project_relations=project_relations,
        project_bindings=project_bindings,
    )
    # Locally-owned ids that are referenced AND owned by commons are a cross-scope
    # situation (design §B3): record commons' owner row, but do NOT load a duplicate
    # entity. Everything else loads as before.
    locally_owned = set(identity_table)
    referenced_local = referenced_ids & locally_owned
    referenced_ids.difference_update(identity_table)

    pending_ids = referenced_ids | (set(overlays) - set(identity_table))

    commons_owner_collisions: list[tuple[str, SourceRef]] = []
    if referenced_local:
        # Resolve commons root lazily only when there is something to check.
        commons_root = resolve_commons_root()
        if commons_root.is_dir():
            query = CommonsQuery(commons_root, warn_stale=False)
            for cid in sorted(referenced_local):
                try:
                    record = query.show(cid)
                except CommonsEntityError:
                    continue  # commons does not own it -> not a cross-scope owner
                commons_owner_collisions.append(
                    (
                        cid,
                        SourceRef(
                            adapter_name="commons-merged", path=_commons_source_ref_path(record.type, record.slug)
                        ),
                    )
                )

    if not pending_ids:
        return [], {}, commons_owner_collisions

    commons_root = resolve_commons_root()
    if not commons_root.is_dir():
        raise CommonsRootNotFoundError(commons_root)

    query = CommonsQuery(commons_root, warn_stale=False)
    loaded: list[tuple[Entity, SourceRef]] = []
    overlay_paths: dict[str, str] = {}
    seen_ids: set[str] = set()
    resolved_ids: set[str] = set(identity_table)
    while pending_ids:
        canonical_id = sorted(pending_ids)[0]
        pending_ids.remove(canonical_id)
        if canonical_id in seen_ids or canonical_id in resolved_ids:
            continue
        seen_ids.add(canonical_id)
        overlay = overlays.get(canonical_id)
        try:
            record = query.show(canonical_id)
        except CommonsEntityError as exc:
            if overlay is not None:
                raise OverlayValidationError(
                    overlay.overlay_path,
                    canonical_id=canonical_id,
                    cause=exc,
                ) from exc
            continue

        policy = read_merge_policy(parse_profile(record.schema_profile))
        validate_overlay_pin(record, overlay)
        merged = merge_entity(record, overlay, policy)
        entity = _materialize_commons_entity(
            merged,
            registry=registry,
            project_slug=project_slug,
            active_kinds=active_kinds,
            ontology_catalogs=ontology_catalogs,
        )
        ref = SourceRef(
            adapter_name="commons-merged",
            path=_commons_source_ref_path(record.type, record.slug),
        )
        loaded.append((entity, ref))
        resolved_ids.add(canonical_id)
        if overlay is not None:
            overlay_paths[canonical_id] = str(overlay.overlay_path)
        transitive_ids = collect_referenced_commons_ids(
            project_root=project_root,
            project_entities=[entity],
            project_relations=[],
            project_bindings=[],
        )
        pending_ids.update(transitive_ids - resolved_ids - seen_ids)

    return loaded, overlay_paths, commons_owner_collisions


def collect_referenced_commons_ids(
    *,
    project_root: Path | None = None,
    project_entities: list[Entity],
    project_relations: list[SourceRelation],
    project_bindings: list[BindingSource],
) -> set[str]:
    """Return commons canonical IDs referenced by project graph sources."""
    found: set[str] = set()
    for entity in project_entities:
        for field_name in (*_AUDITED_LIST_FIELDS, *_MATERIALIZED_LIST_FIELDS):
            for raw in getattr(entity, field_name, None) or []:
                _maybe_add(found, raw)
        _maybe_add(found, getattr(entity, "audits", None))
        for usage in getattr(entity, "dataset_usage", None) or []:
            _maybe_add(found, getattr(usage, "ref", None))
        if getattr(entity, "kind", None) == "paper":
            for raw in getattr(entity, "datasets", None) or []:
                _maybe_add(found, raw)
        derivation = getattr(entity, "derivation", None)
        for raw in getattr(derivation, "inputs", None) or []:
            _maybe_add(found, raw)
        if project_root is not None:
            _collect_geneset_row_usage_refs(found, project_root=project_root, entity=entity)

    for relation in project_relations:
        _maybe_add(found, relation.subject)
        _maybe_add(found, relation.object)

    for binding in project_bindings:
        _maybe_add(found, binding.model)
        _maybe_add(found, binding.parameter)
        for raw in binding.source_refs:
            _maybe_add(found, raw)

    return found


def _collect_geneset_row_usage_refs(found: set[str], *, project_root: Path, entity: Entity) -> None:
    if getattr(entity, "kind", None) != "dataset":
        return
    file_path = getattr(entity, "file_path", None)
    if not isinstance(file_path, str) or not file_path:
        return
    rel_path = Path(file_path)
    fm = geneset_resource_frontmatter(project_root, rel_path)
    if fm is None:
        return
    raw_rows = read_member_rows(project_root, fm)
    if raw_rows is None or isinstance(raw_rows, Exception):
        return
    try:
        rows = parse_geneset_rows(raw_rows)
    except GenesetCollectionError:
        return
    for row in rows:
        for usage in row.dataset_usage:
            _maybe_add(found, usage.get("ref"))


def _materialize_commons_entity(
    merged: MergedEntity,
    *,
    registry: EntityRegistry,
    project_slug: str,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> Entity:
    fm = dict(merged.merged_frontmatter)
    raw_kind = fm.get("kind") or fm.get("type")
    if not isinstance(raw_kind, str) or not raw_kind:
        canonical_id = fm.get("id")
        raise CommonsEntityError(
            merged.canonical.body_path,
            canonical_id=canonical_id if isinstance(canonical_id, str) else None,
            cause=ValueError("missing type/kind"),
        )
    kind = _normalize_kind(raw_kind)
    schema = registry.resolve(kind)
    raw: dict[str, object] = dict(fm)
    raw["kind"] = kind
    raw["canonical_id"] = fm["id"]
    if "description" in fm and "summary" not in fm:
        raw["summary"] = fm["description"]
    if kind == "paper" and "journal" in fm and not raw.get("venue"):
        raw["venue"] = fm["journal"]
    raw["scope"] = "shared"
    raw["profile"] = "shared"
    raw["file_path"] = str(merged.canonical.body_path)
    for overlay_only in _OVERLAY_ONLY_FIELDS:
        raw.pop(overlay_only, None)
    raw.pop("schema_profile", None)
    _enrich_raw(
        raw,
        kind=kind,
        project_slug=project_slug,
        local_profile="shared",
        active_kinds=active_kinds,
        ontology_catalogs=ontology_catalogs,
    )
    return schema.model_validate(raw)


def _commons_source_ref_path(type_name: str, slug: str) -> str:
    type_dir = _TYPE_TO_DIR[type_name]
    if type_name == "dataset":
        return f"commons://{type_dir}/{slug}/entity.md"
    return f"commons://{type_dir}/{slug}.md"


def _maybe_add(found: set[str], raw: object) -> None:
    if not isinstance(raw, str):
        return
    if not raw:
        return
    if is_external_reference(raw):
        return
    if is_metadata_reference(raw):
        return
    if ":" not in raw:
        return
    prefix, value = raw.split(":", 1)
    if prefix in _COMMONS_TYPES:
        if value:
            found.add(raw)
        return
    # Scoped reference form commons:<kind>:<slug> (design §B3a): strip the leading
    # "commons" scope and collect the underlying commons id, so a scoped ref pulls
    # and records its commons owner. (Only the "commons" scope is recognized here;
    # project-name and federated scopes are out of scope until t068.)
    if prefix == "commons" and ":" in value:
        inner_prefix, inner_value = value.split(":", 1)
        if inner_prefix in _COMMONS_TYPES and inner_value:
            found.add(value)
