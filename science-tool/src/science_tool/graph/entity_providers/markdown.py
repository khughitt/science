"""MarkdownProvider — refactor of the existing _load_markdown_entities loader.

Walks the configured scan roots for *.md files; uses parse_entity_file to
extract Entity; lifts each into an EntityRecord and runs _normalize_record.
Behavior matches existing _load_markdown_entities (verified by the snapshot
regression test).
"""

from __future__ import annotations

import re
from pathlib import Path

from science_model.frontmatter import parse_entity_file, parse_frontmatter

from science_tool.graph.entity_providers.base import EntityDiscoveryContext, EntityProvider
from science_tool.graph.entity_providers.record import EntityRecord, _normalize_record, load_reasoning_metadata
from science_tool.graph.source_types import SourceEntity

_SHORT_ID_RE = re.compile(r"^(?P<token>[a-z]\d+)(?:[-_].*)?$", re.IGNORECASE)


def _aliases_from_source_path(kind: str, source_path: str) -> list[str]:
    """Mirror _aliases_from_source_path from sources.py.

    Generates short-token aliases from the file stem for hypothesis/question/task kinds.
    These are added to the raw_aliases list before passing to _normalize_record so that
    _derive_aliases in record.py can deduplicate them alongside canonical_id-derived tokens.
    """
    if kind not in {"hypothesis", "question", "task"}:
        return []

    stem = Path(source_path).stem
    match = _SHORT_ID_RE.match(stem)
    if match is None:
        head = stem.split("-", 1)[0]
        match = _SHORT_ID_RE.match(head)
    if match is None:
        return []

    token = match.group("token")
    return [
        f"{kind}:{token.lower()}",
        f"{kind}:{token.upper()}",
        token.lower(),
        token.upper(),
    ]


class MarkdownProvider(EntityProvider):
    name = "markdown"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        # Roots relative to project_root. Defaults match the existing convention.
        self._scan_roots = scan_roots or ["doc", "specs", "research/packages"]

    def discover(self, ctx: EntityDiscoveryContext) -> list[SourceEntity]:
        entities: list[SourceEntity] = []
        for rel in self._scan_roots:
            root = ctx.project_root / rel
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.md")):
                entity = parse_entity_file(path, project_slug=ctx.project_slug)
                if entity is None:
                    continue
                record = self._extract_record(path, entity, ctx)
                source_entity = _normalize_record(record, ctx, provider_name=self.name)
                # content_preview is not yet wired through EntityRecord/_normalize_record
                # (that's Task 4.2). Carry it from entity directly to preserve byte-identical
                # behavior when this provider replaces _load_markdown_entities in Task 3.1.
                source_entity = source_entity.model_copy(update={"content_preview": entity.content_preview})
                entities.append(source_entity)
        return entities

    def _extract_record(self, path: Path, entity, ctx: EntityDiscoveryContext) -> EntityRecord:
        """Build EntityRecord from the parsed Entity. Mirrors what _load_markdown_entities did inline."""
        raw_aliases: list[str] = []
        raw_profile: str | None = None
        fm_dict: dict[str, object] | None = None

        fm_result = parse_frontmatter(path)
        if fm_result is not None:
            fm, _ = fm_result
            fm_dict = fm
            aliases = fm.get("aliases") or []
            if isinstance(aliases, list):
                raw_aliases = [str(a) for a in aliases]
            profile = fm.get("profile")
            if isinstance(profile, str) and profile.strip():
                raw_profile = profile

        # Include source_path-derived aliases (mirrors _aliases_from_source_path in sources.py).
        # _normalize_record's _derive_aliases will deduplicate against canonical_id-derived tokens.
        path_aliases = _aliases_from_source_path(entity.type.value, entity.file_path)
        combined_aliases = [*raw_aliases, *path_aliases]

        return EntityRecord(
            canonical_id=entity.canonical_id,
            kind=entity.type.value,
            title=entity.title,
            source_path=entity.file_path,
            profile=raw_profile,  # None → normalizer applies _default_profile_for_kind
            domain=entity.domain,
            related=list(entity.related or []),
            source_refs=list(entity.source_refs or []),
            ontology_terms=list(entity.ontology_terms or []),
            aliases=combined_aliases,
            same_as=list(entity.same_as or []),
            status=entity.status,
            confidence=entity.confidence,
            extra=load_reasoning_metadata(fm_dict, source_path=path),
        )
