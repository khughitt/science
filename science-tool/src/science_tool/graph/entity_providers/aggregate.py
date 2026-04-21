"""AggregateProvider — refactor of the existing _load_structured_entities loader.

Multi-type aggregate (entities.yaml): one file lists papers, concepts, etc., each
entry has a `kind:` field. Single-type aggregate (doc/<plural>/<plural>.{json,yaml})
is added in Task 5.1.

Behavioral fidelity notes vs _load_structured_entities in sources.py:
- source_path: honoured from item dict first; defaults to
  "knowledge/sources/{local_profile}/entities.yaml" (matches _default_local_source_path).
- profile: item.get("profile") or local_profile — NOT _default_profile_for_kind.
  (sources.py uses local_profile as fallback, not the core/ontology logic.)
- content_preview: propagated via model_copy after _normalize_record.
- reasoning metadata (claim_layer, identification_strength, etc.): propagated via
  model_copy after _normalize_record.
- literature-ref canonicalization: applied to related/source_refs/same_as/blocked_by.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from science_model.reasoning import (
    ClaimLayer,
    EvidenceRole,
    IdentificationStrength,
    MeasurementModel,
    ProxyDirectness,
    RivalModelPacket,
    SupportScope,
)

from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.entity_providers.record import EntityRecord, _normalize_record
from science_tool.graph.source_types import SourceEntity
from science_tool.big_picture.literature_prefix import canonical_paper_id

_REASONING_FIELDS: dict[str, type] = {
    "claim_layer": ClaimLayer,
    "identification_strength": IdentificationStrength,
    "proxy_directness": ProxyDirectness,
    "supports_scope": SupportScope,
    "independence_group": str,
    "evidence_role": EvidenceRole,
    "measurement_model": MeasurementModel,
    "rival_model_packet": RivalModelPacket,
}


def _local_profile_sources_dir(project_root: Path, *, local_profile: str) -> Path:
    """Mirror the existing helper from graph/sources.py."""
    return project_root / "knowledge" / "sources" / local_profile


def _default_source_path(local_profile: str) -> str:
    """Mirror _default_local_source_path from sources.py."""
    return f"knowledge/sources/{local_profile}/entities.yaml"


def _canonicalize_literature_refs(values: list[str]) -> list[str]:
    """Mirror _canonicalize_literature_refs from sources.py."""
    return [canonical_paper_id(v) for v in values]


def _coerce_string_list(value: object) -> list[str]:
    """Mirror _coerce_string_list from sources.py."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _extract_reasoning_metadata(raw: dict) -> dict[str, object]:
    """Extract reasoning metadata fields from a raw item dict.

    Mirrors _load_reasoning_metadata from sources.py but returns only valid values.
    Enum fields are validated; invalid values are silently dropped.
    """
    metadata: dict[str, object] = {}
    for field, field_type in _REASONING_FIELDS.items():
        value = raw.get(field)
        if value is None:
            continue
        if field_type is not str and isinstance(value, str):
            try:
                field_type(value)
            except ValueError:
                continue
        metadata[field] = value
    return metadata


class AggregateProvider(EntityProvider):
    name = "aggregate"

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        entities.extend(self._load_multi_type_aggregate(ctx))
        entities.extend(self._load_single_type_aggregates(ctx))
        return entities

    def _load_multi_type_aggregate(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities_path = _local_profile_sources_dir(ctx.project_root, local_profile=ctx.local_profile) / "entities.yaml"
        if not entities_path.is_file():
            return []
        try:
            data = yaml.safe_load(entities_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return []
        items = data.get("entities") or []
        if not isinstance(items, list):
            return []
        default_source_path = _default_source_path(ctx.local_profile)
        results: list[SourceEntity] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            entity = self._entity_from_dict(raw, ctx=ctx, default_source_path=default_source_path)
            if entity is None:
                continue
            results.append(entity)
        return results

    def _entity_from_dict(
        self,
        raw: dict,
        *,
        ctx: EntityDiscoveryContext,
        default_source_path: str,
    ) -> SourceEntity | None:
        """Build a SourceEntity from an aggregate-entry dict; return None if invalid."""
        canonical_id = raw.get("canonical_id")
        kind = raw.get("kind")
        title = raw.get("title")
        if not isinstance(canonical_id, str) or not canonical_id:
            return None
        if not isinstance(kind, str) or not kind:
            return None
        if not isinstance(title, str) or not title:
            return None

        # source_path: item dict takes precedence, else default
        source_path = str(raw.get("source_path") or default_source_path)

        # profile: item dict takes precedence, else local_profile (NOT _default_profile_for_kind)
        profile = str(raw.get("profile") or ctx.local_profile)

        aliases_raw = raw.get("aliases") or []
        aliases = [str(a) for a in aliases_raw] if isinstance(aliases_raw, list) else []

        record = EntityRecord(
            canonical_id=canonical_id,
            kind=kind,
            title=title,
            source_path=source_path,
            description=str(raw.get("description") or ""),
            profile=profile,
            domain=raw.get("domain") if isinstance(raw.get("domain"), str) else None,
            confidence=_coerce_optional_float(raw.get("confidence")),
            status=str(raw.get("status")) if raw.get("status") is not None else None,
            related=_canonicalize_literature_refs(_coerce_string_list(raw.get("related"))),
            blocked_by=_canonicalize_literature_refs(_coerce_string_list(raw.get("blocked_by"))),
            source_refs=_canonicalize_literature_refs(_coerce_string_list(raw.get("source_refs"))),
            ontology_terms=_coerce_string_list(raw.get("ontology_terms")),
            same_as=_canonicalize_literature_refs(_coerce_string_list(raw.get("same_as"))),
            aliases=aliases,
        )

        try:
            entity = _normalize_record(record, ctx, provider_name=self.name)
        except Exception:
            return None

        # content_preview and reasoning metadata are not yet wired through
        # EntityRecord/_normalize_record (Task 4.2). Propagate via model_copy to
        # preserve byte-identical behavior when this provider replaces
        # _load_structured_entities in Task 3.1.
        updates: dict[str, object] = {}

        content_preview = str(raw.get("content_preview") or "")
        if content_preview:
            updates["content_preview"] = content_preview

        reasoning = _extract_reasoning_metadata(raw)
        updates.update(reasoning)

        if updates:
            entity = entity.model_copy(update=updates)

        return entity

    def _load_single_type_aggregates(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        from science_model.frontmatter import _DIR_TO_TYPE

        results: list[SourceEntity] = []
        for plural, singular in _DIR_TO_TYPE.items():
            for ext in ("json", "yaml"):
                f = ctx.project_root / "doc" / plural / f"{plural}.{ext}"
                if not f.is_file():
                    continue
                items = self._load_list(f)
                try:
                    rel_path = str(f.relative_to(ctx.project_root))
                except ValueError:
                    rel_path = str(f)
                for raw in items:
                    if not isinstance(raw, dict):
                        continue
                    record = self._record_from_dict(raw, kind=singular, source_path=rel_path)
                    if record is None:
                        continue
                    results.append(_normalize_record(record, ctx, provider_name=self.name))
        return results

    def _load_list(self, path: Path) -> list:
        """Read a list from a JSON or YAML file. Returns empty list on read failure."""
        try:
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                data = json.loads(text)
            else:
                data = yaml.safe_load(text)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, yaml.YAMLError, OSError):
            return []

    def _record_from_dict(self, raw: dict, *, kind: str, source_path: str) -> EntityRecord | None:
        """Build an EntityRecord from a single-type aggregate entry dict.

        The `kind` parameter is the inferred type (from the filename); `raw` entries do not
        need a `kind:` field. The canonical_id is read from `id` or `canonical_id`.
        Returns None if required fields are missing.
        """
        canonical_id = raw.get("id") or raw.get("canonical_id")
        title = raw.get("title")
        if not isinstance(canonical_id, str) or not canonical_id:
            return None
        if not isinstance(title, str) or not title:
            return None

        aliases_raw = raw.get("aliases") or []
        aliases = [str(a) for a in aliases_raw] if isinstance(aliases_raw, list) else []

        return EntityRecord(
            canonical_id=canonical_id,
            kind=kind,
            title=title,
            source_path=source_path,
            description=str(raw.get("description") or ""),
            profile=str(raw.get("profile")) if raw.get("profile") is not None else None,
            domain=raw.get("domain") if isinstance(raw.get("domain"), str) else None,
            confidence=_coerce_optional_float(raw.get("confidence")),
            status=str(raw.get("status")) if raw.get("status") is not None else None,
            related=_canonicalize_literature_refs(_coerce_string_list(raw.get("related"))),
            blocked_by=_canonicalize_literature_refs(_coerce_string_list(raw.get("blocked_by"))),
            source_refs=_canonicalize_literature_refs(_coerce_string_list(raw.get("source_refs"))),
            ontology_terms=_coerce_string_list(raw.get("ontology_terms")),
            same_as=_canonicalize_literature_refs(_coerce_string_list(raw.get("same_as"))),
            aliases=aliases,
        )


def _coerce_optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
