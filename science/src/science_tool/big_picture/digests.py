# src/science_tool/big_picture/digests.py
"""Tier 4 (P5): big-picture digest-awareness leaf.

Reads live ``report_kind: cluster-digest`` synthesis entities and the archive
index to support consumer substitution in the big-picture programmatic surfaces.
Pure read-only helpers; index-only descent (``ArchiveRow`` fields) per the P5 design.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from science_tool.archive import ArchiveRow, load_archive_index
from science_tool.big_picture.frontmatter import as_list, read_frontmatter
from science_tool.big_picture.layout import entity_dir
from science_tool.consolidate import (
    CLUSTER_DIGEST_REPORT_KIND,
    SYNTHESIS_KIND,
    consolidates_targets,
)
from science_tool.entities import is_default_visible


@dataclass(frozen=True)
class MemberSummary:
    """Index-only view of one archived, consolidated member."""

    id: str
    kind: str | None
    title: str | None
    digest_insight: str | None
    archived: bool


@dataclass(frozen=True)
class ClusterDigest:
    """A live ``report_kind: cluster-digest`` synthesis entity."""

    id: str
    title: str | None
    related: list[str] = field(default_factory=list)
    member_ids: list[str] = field(default_factory=list)
    member_count: int = 0
    members: list[MemberSummary] = field(default_factory=list)


def redirect_refs(refs: Iterable[str], remap: Mapping[str, str]) -> list[str]:
    """Rewrite each ref through ``remap`` (archived member id -> digest id),
    pass-through otherwise; de-dup preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for ref in refs:
        target = remap.get(ref, ref)
        if target not in seen:
            seen.add(target)
            out.append(target)
    return out


def member_to_digest(project_root: Path) -> dict[str, str]:
    """``member_id -> digest_id`` built from the ACTIVE archive index.

    For each active ``ArchiveRow`` whose ``consolidated_into`` is set, map
    ``row.id`` plus each of ``row.aliases`` / ``row.same_as`` to
    ``consolidated_into``. Building from the index (not from digest
    ``sci:consolidates`` relations) guarantees only genuinely-archived members
    redirect; a scaffolded-but-unapplied digest's members are absent from the index
    and resolve normally as live.

    Raises ``ValueError`` if a key maps to two different digests — an index
    integrity violation P4 ``apply_consolidation`` makes impossible for applied
    members (it fails loud on an already-archived member)."""
    index = load_archive_index(project_root)
    out: dict[str, str] = {}
    for canonical, row in index.active_by_id.items():
        digest = row.consolidated_into
        if not digest:
            continue
        for key in (canonical, *row.aliases, *row.same_as):
            existing = out.get(key)
            if existing is not None and existing != digest:
                raise ValueError(
                    f"member {key!r} maps to two digests: {existing!r} and {digest!r}"
                )
            out[key] = digest
    return out


def _member_summary(
    member_id: str,
    resolvable: Mapping[str, str],
    active: Mapping[str, ArchiveRow],
) -> MemberSummary:
    """Index-only summary for one consolidated member. The member id is resolved
    through ``resolvable`` (alias/same_as -> canonical) before the active-index
    lookup, so a digest that names a member by an alias still descends to the
    archived row — symmetric with ``member_to_digest``. ``archived=False`` when the
    member is absent (e.g. a scaffolded-but-unapplied digest whose members are live)."""
    row = active.get(resolvable.get(member_id, member_id))
    if row is None:
        return MemberSummary(id=member_id, kind=None, title=None, digest_insight=None, archived=False)
    return MemberSummary(
        id=member_id, kind=row.kind, title=row.title,
        digest_insight=row.digest_insight, archived=True)


def load_cluster_digests(project_root: Path, *, deep: bool = False) -> dict[str, ClusterDigest]:
    """Scan ``entities/synthesis/`` for visible ``report_kind: cluster-digest``
    entities. ``member_ids`` come from each digest's ``sci:consolidates`` relations.
    When ``deep`` is True, each member is resolved against the active archive index
    into a ``MemberSummary`` (``archived=False`` when the id is absent — e.g. a
    scaffolded-but-unapplied digest whose members are still live)."""
    directory = entity_dir(project_root, SYNTHESIS_KIND)
    if not directory.is_dir():
        return {}
    index = load_archive_index(project_root) if deep else None
    resolvable = index.resolvable_ids() if index is not None else {}
    active = index.active_by_id if index is not None else {}
    out: dict[str, ClusterDigest] = {}
    for path in sorted(directory.glob("*.md")):
        fm = read_frontmatter(path)
        if not fm or "id" not in fm:
            continue
        if fm.get("report_kind") != CLUSTER_DIGEST_REPORT_KIND:
            continue
        if not is_default_visible(fm.get("status")):
            continue
        member_ids = consolidates_targets(fm)
        members = (
            [_member_summary(mid, resolvable, active) for mid in member_ids]
            if deep else []
        )
        digest_id = str(fm["id"])
        title = str(fm["title"]) if fm.get("title") is not None else None
        out[digest_id] = ClusterDigest(
            id=digest_id, title=title, related=as_list(fm.get("related")),
            member_ids=member_ids, member_count=len(member_ids), members=members)
    return out
