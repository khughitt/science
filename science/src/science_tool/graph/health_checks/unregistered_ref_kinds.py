"""Unregistered-ref-kinds health check: identity refs with an unregistered CURIE prefix."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from science_tool.graph.entity_registry import EntityKindNotRegisteredError
from science_tool.graph.health_checks.base import (
    IDENTITY_REFERENCE_FIELDS,
    NO_ENTITIES_REASON,
    PROJECT_SOURCES_EMPTY,
    HealthCheck,
    context_sources,
)
from science_tool.graph.sources import (
    ProjectSources,
    external_prefixes,
    is_bibliography_reference,
    is_external_reference,
    is_metadata_reference,
    load_project_sources,
)
from science_tool.instruments import InstrumentResult


class UnregisteredRefKind(TypedDict):
    kind: str
    field: str
    mention_count: int
    refs: list[str]
    sources: list[str]


class _UnregisteredRefKindAccumulator(TypedDict):
    mention_count: int
    refs: set[str]
    sources: set[str]


_BIBLIOGRAPHY_REFERENCE_FIELDS = frozenset({"source_refs", "evidence_refs"})


def collect_unregistered_ref_kinds(
    project_root: Path, *, sources: ProjectSources | None = None
) -> InstrumentResult[UnregisteredRefKind]:
    """Report identity refs whose CURIE prefix is not a registered entity kind.

    ``unwired`` when the load produced no entities — there were no refs to inspect.
    """
    if sources is None:
        sources = load_project_sources(project_root.resolve())
    if not sources.entities:
        return InstrumentResult.unwired(code=PROJECT_SOURCES_EMPTY, reason=NO_ENTITIES_REASON)
    external = external_prefixes(sources.ontology_catalogs)
    peer_ids = sources.peer_ids
    grouped: dict[tuple[str, str], _UnregisteredRefKindAccumulator] = {}

    for entity in sources.entities:
        source_path = entity.file_path
        for field in IDENTITY_REFERENCE_FIELDS:
            for raw in _string_refs(getattr(entity, field, None)):
                if (
                    ":" not in raw
                    or is_metadata_reference(raw)
                    or (field == "source_refs" and raw.startswith("annotation:"))
                    or (field in _BIBLIOGRAPHY_REFERENCE_FIELDS and is_bibliography_reference(raw))
                    or is_external_reference(raw)
                    or is_external_reference(raw, known_prefixes=external)
                    or _is_registered_peer_address(raw, peer_ids)
                ):
                    continue
                kind, _ = raw.split(":", 1)
                kind = kind.lower()
                try:
                    sources.registry.kind_class(kind)
                except EntityKindNotRegisteredError:
                    bucket = grouped.setdefault(
                        (kind, field),
                        {"mention_count": 0, "refs": set(), "sources": set()},
                    )
                    bucket["mention_count"] += 1
                    bucket["refs"].add(raw)
                    bucket["sources"].add(source_path)

    rows: list[UnregisteredRefKind] = []
    for (kind, field), bucket in grouped.items():
        rows.append(
            {
                "kind": kind,
                "field": field,
                "mention_count": bucket["mention_count"],
                "refs": sorted(bucket["refs"]),
                "sources": sorted(bucket["sources"]),
            }
        )
    return InstrumentResult.from_rows(sorted(rows, key=lambda row: (row["kind"], row["field"])))


def _is_registered_peer_address(raw: str, peer_ids: frozenset[str]) -> bool:
    if not peer_ids or ":" not in raw:
        return False
    scope, artifact = raw.split(":", 1)
    return ":" in artifact and scope in peer_ids


def _string_refs(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if isinstance(item, str)]
    return []


CHECK = HealthCheck(
    name="unregistered_ref_kinds",
    description="Find identity refs whose prefix is not a registered entity kind.",
    requires_sources=True,
    run=lambda context: collect_unregistered_ref_kinds(context.project_root, sources=context_sources(context)),
    empty=lambda _root: [],
)
