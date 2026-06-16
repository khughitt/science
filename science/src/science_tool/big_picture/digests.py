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

from science_tool.archive import load_archive_index
from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.layout import entity_dir
from science_tool.consolidate import (
    CLUSTER_DIGEST_REPORT_KIND,
    CONSOLIDATES_PREDICATE,
    SYNTHESIS_KIND,
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


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _consolidates_targets(fm: dict) -> list[str]:
    """Member ids = targets of the digest's ``sci:consolidates`` relations, read off
    the frontmatter dict in the same shape P4 ``scaffold_digest`` writes."""
    targets: list[str] = []
    for rel in fm.get("relations") or []:
        if isinstance(rel, dict) and rel.get("predicate") == CONSOLIDATES_PREDICATE:
            target = rel.get("target")
            if isinstance(target, str):
                targets.append(target)
    return targets


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
