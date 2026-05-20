"""Collect commons references needed by graph builds.

Graph loading can depend on Science Commons entries, but commons loading
must remain independent of project graph materialization. This module keeps
that dependency one-way by extracting referenced commons IDs from already
loaded project graph sources without performing I/O or commons access.
"""

from __future__ import annotations

from science_model.entities import Entity
from science_model.ontologies.schema import OntologyCatalog
from science_model.source_contracts import BindingSource

from science_tool.commons.overlay import MergedEntity
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import (
    SourceRelation,
    _enrich_raw,
    _normalize_kind,
    is_external_reference,
    is_metadata_reference,
)

_COMMONS_TYPES = frozenset({"dataset", "paper", "topic", "theme"})
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
