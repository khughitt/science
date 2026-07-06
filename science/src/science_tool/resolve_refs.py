from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from science_tool.entities import list_entities
from science_tool.questions import slugify

# Kinds resolved against — the same set `science project index` exposes.
_INDEX_KINDS = ("hypothesis", "question")


def _safe_slug(text: str) -> str:
    """slugify() but empty-safe: blank/normalization-empty input -> '' (never raises)."""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        return slugify(text)
    except ValueError:
        return ""


@dataclass(frozen=True)
class Resolution:
    query: str
    resolved: str | None
    match_kind: str  # id-exact | id-slug | title-slug | ambiguous | unresolved
    candidates: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "resolved": self.resolved,
            "match_kind": self.match_kind,
            "candidates": list(self.candidates),
        }


@dataclass(frozen=True)
class _Entry:
    entity_id: str
    id_slug: str
    title_slug: str


@dataclass(frozen=True)
class RefIndex:
    entries: tuple[_Entry, ...]

    def resolve(self, query: str) -> Resolution:
        q = (query or "").strip()
        # Tier 1: id-exact (canonical ids are unique).
        for entry in self.entries:
            if entry.entity_id == q:
                return Resolution(query, entry.entity_id, "id-exact", (entry.entity_id,))
        qslug = _safe_slug(q)
        if not qslug:
            return Resolution(query, None, "unresolved", ())
        # Tier 2: query slug is a substring of an entity's id-slug.
        id_hits = tuple(sorted({e.entity_id for e in self.entries if qslug in e.id_slug}))
        if id_hits:
            return _from_hits(query, id_hits, "id-slug")
        # Tier 3: query slug is a substring of an entity's title-slug.
        title_hits = tuple(sorted({e.entity_id for e in self.entries if qslug in e.title_slug}))
        if title_hits:
            return _from_hits(query, title_hits, "title-slug")
        return Resolution(query, None, "unresolved", ())


def _from_hits(query: str, hits: tuple[str, ...], match_kind: str) -> Resolution:
    if len(hits) == 1:
        return Resolution(query, hits[0], match_kind, hits)
    return Resolution(query, None, "ambiguous", hits)


def build_ref_index(rows: Iterable[Mapping[str, object]]) -> RefIndex:
    entries: list[_Entry] = []
    for row in rows:
        entity_id = str(row["id"])
        local = entity_id.split(":", 1)[1] if ":" in entity_id else entity_id
        entries.append(
            _Entry(
                entity_id=entity_id,
                id_slug=_safe_slug(local),
                title_slug=_safe_slug(str(row.get("title") or "")),
            )
        )
    return RefIndex(entries=tuple(entries))


def load_index_rows(project_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for kind in _INDEX_KINDS:
        for entity in list_entities(project_root, kind=kind):
            rows.append({"id": str(entity["id"]), "title": str(entity["title"])})
    return rows
