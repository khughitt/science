"""DatapackageDirectoryProvider — datasets promoted to live as data/<slug>/datapackage.yaml.

Walks for **/datapackage.yaml under data/ and results/. Filters strictly: only datapackages
whose profiles[] includes "science-pkg-entity-1.0" are emitted as entities. Datapackages
without that profile are silently ignored (existing behavior for the non-entity case).

Hard-error contract: an entity-profile datapackage with valid YAML but missing required
fields (id, type, title) raises EntityDatapackageInvalidError. Silently dropping a promoted
entity would be worse than failing.
"""

from __future__ import annotations

import yaml

from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.entity_providers.record import EntityRecord, _normalize_record
from science_tool.graph.source_types import EntityDatapackageInvalidError, SourceEntity


class DatapackageDirectoryProvider(EntityProvider):
    name = "datapackage-directory"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        self._scan_roots = scan_roots or ["data", "results"]

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        for rel in self._scan_roots:
            root = ctx.project_root / rel
            if not root.is_dir():
                continue
            for dp_path in sorted(root.rglob("datapackage.yaml")):
                try:
                    rel_path = str(dp_path.relative_to(ctx.project_root))
                except ValueError:
                    rel_path = str(dp_path)
                try:
                    dp = yaml.safe_load(dp_path.read_text(encoding="utf-8")) or {}
                except (yaml.YAMLError, OSError):
                    continue
                profiles = dp.get("profiles") or []
                if "science-pkg-entity-1.0" not in profiles:
                    continue
                self._validate_required_fields(rel_path, dp)
                record = self._extract_record(rel_path, dp)
                entities.append(_normalize_record(record, ctx, provider_name=self.name))
        return entities

    def _validate_required_fields(self, source_path: str, dp: dict) -> None:
        """Hard-error when a science-pkg-entity-1.0 datapackage is missing required fields."""
        for field in ("id", "type", "title"):
            if not dp.get(field):
                raise EntityDatapackageInvalidError(
                    source_path,
                    f"missing required entity field {field!r} (science-pkg-entity-1.0 profile present)",
                )

    def _extract_record(self, source_path: str, dp: dict) -> EntityRecord:
        return EntityRecord(
            canonical_id=str(dp["id"]),
            kind=str(dp["type"]),
            title=str(dp["title"]),
            description=str(dp.get("description", "")),
            source_path=source_path,
            ontology_terms=list(dp.get("ontology_terms") or []),
            related=list(dp.get("related") or []),
            source_refs=list(dp.get("source_refs") or []),
            status=dp.get("status"),
            extra={
                "origin": dp.get("origin"),
                "tier": dp.get("tier"),
                "access": dp.get("access"),
                "derivation": dp.get("derivation"),
                "datapackage_path": source_path,
            },
        )
