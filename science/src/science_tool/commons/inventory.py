"""Build the inventory_v2 payload for the whole commons store.

Walks the commons store via CommonsEntityAdapter, projects each canonical
entity as an InventoryEntity with scope="cross-project", and (Task 7) projects
dataset resources into data["resources"]. Per-entity problems become
InventoryWarning entries; the only hard failure is a missing commons root.
"""

from __future__ import annotations

from datetime import UTC, datetime

from science_model.contracts.inventory_v2 import (
    InventoryAlias,
    InventoryEntity,
    InventoryPayload,
    InventoryReference,
    InventorySourceLocation,
    InventoryWarning,
    finalize_inventory_payload,
)

from science_tool.commons.adapter import CommonsEntityAdapter, CommonsEntityRecord
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsLayoutError,
    CommonsRootNotFoundError,
)

_TYPE_DIRS = ("datasets", "papers", "topics", "themes")
_PROMOTED_KEYS = frozenset({"id", "type", "title", "status", "aliases", "related"})


def build_commons_inventory() -> InventoryPayload:
    """Return the inventory_v2 payload describing the whole commons store."""
    root = resolve_commons_root()
    if not root.is_dir():
        raise CommonsRootNotFoundError(root)

    entities: list[InventoryEntity] = []
    aliases: list[InventoryAlias] = []
    warnings: list[InventoryWarning] = []

    for item in CommonsEntityAdapter(root).scan():
        if isinstance(item, CommonsEntityError):
            code = (
                "commons-datapackage-invalid"
                if isinstance(item.cause, CommonsLayoutError)
                else "commons-entity-invalid"
            )
            warnings.append(
                InventoryWarning(
                    code=code,
                    severity="error",
                    message=str(item),
                    path=str(item.path),
                    canonical_id=item.canonical_id,
                )
            )
            continue
        entity, entity_aliases = _entity_from_record(item, warnings)
        entities.append(entity)
        aliases.extend(entity_aliases)

    payload = InventoryPayload(
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        project_id="commons",
        project_path=str(root),
        entities=sorted(entities, key=lambda e: e.id),
        aliases=sorted(aliases, key=lambda a: a.alias),
        overlays=[],
        warnings=warnings,
        watch_paths=[name for name in _TYPE_DIRS if (root / name).is_dir()],
    )
    return finalize_inventory_payload(payload)


def _entity_from_record(
    record: CommonsEntityRecord, warnings: list[InventoryWarning]
) -> tuple[InventoryEntity, list[InventoryAlias]]:
    frontmatter = record.frontmatter
    related = [
        InventoryReference(relation="related", target_id=str(target))
        for target in frontmatter.get("related", [])
        if target
    ]
    entity_aliases = [str(alias) for alias in frontmatter.get("aliases", [])]
    data = {key: value for key, value in frontmatter.items() if key not in _PROMOTED_KEYS}
    entity = InventoryEntity(
        id=record.canonical_id,
        kind=record.type,
        local_id=record.slug,
        title=frontmatter.get("title"),
        status=frontmatter.get("status"),
        scope="cross-project",
        registration_state="unknown",
        source=InventorySourceLocation(adapter="commons-entity", path=str(record.body_path)),
        aliases=entity_aliases,
        related=related,
        data=data,
    )
    aliases = [InventoryAlias(alias=alias, canonical_id=record.canonical_id) for alias in entity_aliases]
    return entity, aliases
