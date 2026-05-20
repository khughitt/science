"""Collect commons references needed by graph builds.

Graph loading can depend on Science Commons entries, but commons loading
must remain independent of project graph materialization. This module keeps
that dependency one-way by extracting referenced commons IDs from already
loaded project graph sources without performing I/O or commons access.
"""

from __future__ import annotations

import logging
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
from science_tool.commons.overlay import MergedEntity, OverlayAdapter, merge_entity
from science_tool.commons.query import CommonsQuery
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import (
    SourceRelation,
    _enrich_raw,
    _normalize_kind,
    is_external_reference,
    is_metadata_reference,
)

logger = logging.getLogger(__name__)

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
) -> tuple[list[tuple[Entity, SourceRef]], dict[str, str]]:
    overlays = {}
    if (project_root / "doc").exists():
        for item in OverlayAdapter(project_root, project_slug).scan():
            if isinstance(item, OverlayValidationError):
                raise item
            overlays[item.canonical_id] = item

    referenced_ids = collect_referenced_commons_ids(
        project_entities=project_entities,
        project_relations=project_relations,
        project_bindings=project_bindings,
    )
    referenced_ids.difference_update(identity_table)

    needed_ids = referenced_ids | set(overlays)
    if not needed_ids:
        return [], {}

    commons_root = resolve_commons_root()
    if not commons_root.is_dir():
        raise CommonsRootNotFoundError(commons_root)

    query = CommonsQuery(commons_root)
    loaded: list[tuple[Entity, SourceRef]] = []
    overlay_paths: dict[str, str] = {}
    for canonical_id in sorted(needed_ids):
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

        if overlay is not None and (overlay.pin_version or overlay.pin_effective_version):
            logger.warning(
                "commons overlay pinning is not enforced for %s at %s",
                canonical_id,
                overlay.overlay_path,
            )

        policy = read_merge_policy(parse_profile(record.schema_profile))
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
        if overlay is not None:
            overlay_paths[canonical_id] = str(overlay.overlay_path)

    return loaded, overlay_paths


def collect_referenced_commons_ids(
    *,
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

    for relation in project_relations:
        _maybe_add(found, relation.subject)
        _maybe_add(found, relation.object)

    for binding in project_bindings:
        _maybe_add(found, binding.model)
        _maybe_add(found, binding.parameter)
        for raw in binding.source_refs:
            _maybe_add(found, raw)

    return found


def _materialize_commons_entity(
    merged: MergedEntity,
    *,
    registry: EntityRegistry,
    project_slug: str,
    active_kinds: frozenset[str],
    ontology_catalogs: list[OntologyCatalog],
) -> Entity:
    fm = dict(merged.merged_frontmatter)
    kind = _normalize_kind(fm["type"])
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
    if prefix not in _COMMONS_TYPES:
        return
    if not value:
        return
    found.add(raw)
