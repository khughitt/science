"""Audit helpers for migrating projects onto canonical graph materialization."""

from __future__ import annotations

from science_model import normalize_alias

from science_tool.graph.sources import (
    AliasCollisionError,
    ProjectSources,
    SourceEntity,
    build_alias_map,
    is_external_reference,
)


def audit_project_sources(sources: ProjectSources) -> tuple[list[dict[str, str]], bool]:
    """Validate that structured project sources resolve canonically."""
    try:
        alias_map = build_alias_map(sources.entities)
    except AliasCollisionError as exc:
        return (
            [
                {
                    "check": "ambiguous_alias",
                    "status": "fail",
                    "source": exc.first_canonical_id,
                    "field": "aliases",
                    "target": exc.alias,
                    "details": f"conflicts with {exc.second_canonical_id}",
                }
            ],
            True,
        )
    rows: list[dict[str, str]] = []

    for entity in sources.entities:
        rows.extend(_audit_entity(entity, alias_map))

    rows.sort(key=lambda row: (row["source"], row["target"]))
    has_failures = any(row["status"] == "fail" for row in rows)
    return rows, has_failures


def _audit_entity(entity: SourceEntity, alias_map: dict[str, str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for target in entity.related:
        rows.extend(_audit_reference(entity, "related", target, alias_map))
    for target in entity.blocked_by:
        rows.extend(_audit_reference(entity, "blocked_by", target, alias_map))
    for target in entity.source_refs:
        rows.extend(_audit_reference(entity, "source_refs", target, alias_map))
    return rows


def _audit_reference(
    entity: SourceEntity,
    field_name: str,
    raw_target: str,
    alias_map: dict[str, str],
) -> list[dict[str, str]]:
    if is_external_reference(raw_target):
        return []

    resolved = normalize_alias(raw_target, alias_map)
    if resolved == raw_target and raw_target not in alias_map:
        return [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": entity.canonical_id,
                "field": field_name,
                "target": raw_target,
                "details": f"{entity.source_path} references an unknown canonical entity",
            }
        ]

    return []
