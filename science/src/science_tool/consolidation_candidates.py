"""Read-only consolidation-candidate detector (P2).

Scans canonical ``entities/`` and reports two kinds of consolidation candidates —
superseded-lineage (mechanical) and semantic clusters (dep-free heuristics) —
each with surfaced evidence. Takes NO action. This is the decision-support
surface for the future ``entities consolidate --apply``. See
docs/user-guide/entities.md for the current operator workflow and
precision-first gating contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from science_tool.consolidation import (
    SupersedesGraph,
    build_supersedes_graph,
    iter_entity_frontmatter,
)
from science_tool.entities import is_default_visible

_SEQ_PREFIX = re.compile(r"^\d+-")
_VERSION_SUFFIX = re.compile(r"-v\d+$")
_TASK_PREFIX = "task:"

# Bases that, on their own, mark a merged cluster as a genuine consolidation
# candidate (redundancy, not mere shared topic). `task-family` and a *single*
# `shared-anchor` are corroborating-only — they enrich a qualifying cluster's
# evidence but never qualify one by themselves. See the §7.1 tuning revision: the
# validation round showed task-family / single-anchor produce ~95% topical noise.
_PRIMARY_BASES = frozenset({"id-stem", "group", "related-overlap"})


class LinearChain(BaseModel):
    survivor: str
    archivable: list[str]  # the superseded tail (everything but the survivor); alphabetically sorted, NOT topological depth-order
    members: list[str]     # all nodes including the survivor; alphabetically sorted


class NonLinearChain(BaseModel):
    nodes: list[str]  # component nodes, alphabetically sorted
    reason: str


class SemanticCluster(BaseModel):
    signal: str            # "structural-family" | "shared-anchor" | "related-overlap" (merged: joined with "+")
    members: list[str]
    evidence: str


class SupersededLineage(BaseModel):
    linear: list[LinearChain] = Field(default_factory=list)
    non_linear: list[NonLinearChain] = Field(default_factory=list)


class ConsolidationCandidates(BaseModel):
    project_root: str
    superseded_lineage: SupersededLineage = Field(default_factory=SupersededLineage)
    semantic_clusters: list[SemanticCluster] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


@dataclass(frozen=True)
class _RawCluster:
    """A single-signal cluster before merge/gating. ``basis`` is the gating tag
    (a structural-family sub-basis, or the signal name for the other two
    detectors); ``signal`` is the public token surfaced to the user."""

    signal: str
    basis: str
    members: tuple[str, ...]
    evidence: str


def _local_part(entity_id: str) -> str:
    return entity_id.split(":", 1)[1] if ":" in entity_id else entity_id


def _id_stem(entity_id: str) -> str:
    local = _local_part(entity_id)
    local = _SEQ_PREFIX.sub("", local)
    local = _VERSION_SUFFIX.sub("", local)
    return local


def _task_refs(fm: dict[str, Any]) -> list[str]:
    """`task:`-prefixed refs from `related:` only. PREFIX-SHAPED BY DESIGN (spec
    §6.2): task entities live in `tasks/` (outside the `entities/` scan), so there
    is no loaded task set to resolve against — any `task:`-prefixed string counts.
    Real task-id resolution is a deferred §7 tuning-round concern, not P2."""
    related = fm.get("related")
    items = related if isinstance(related, list) else []
    return sorted({item for item in items if isinstance(item, str) and item.startswith(_TASK_PREFIX)})


def _structural_family_clusters(
    visible: list[tuple[str, str, dict[str, Any]]],
    min_cluster_size: int,
) -> list[_RawCluster]:
    """Basis-namespaced structural grouping. Keys are (kind, basis, value) so the
    three sub-bases never collide by value; identical member-sets merge later. The
    sub-basis is preserved on the raw cluster so gating can distinguish the
    redundancy-grade `id-stem`/`group` bases from corroborating `task-family`."""
    groups: dict[tuple[str, str, str], list[str]] = {}
    for eid, kind, _fm in visible:
        groups.setdefault((kind, "id-stem", _id_stem(eid)), []).append(eid)
        group_value = _fm.get("group")
        if isinstance(group_value, str) and group_value:
            groups.setdefault((kind, "group", group_value), []).append(eid)
        for task_ref in _task_refs(_fm):
            groups.setdefault((kind, "task-family", task_ref), []).append(eid)

    clusters: list[_RawCluster] = []
    for (kind, basis, value), members in groups.items():
        if len(members) < min_cluster_size:
            continue
        clusters.append(
            _RawCluster(
                signal="structural-family",
                basis=basis,
                members=tuple(sorted(members)),
                evidence=f"{basis} '{value}' (kind {kind}; {len(members)} members)",
            )
        )
    return clusters


def _entity_refs(fm: dict[str, Any], known_ids: set[str], *, fields: tuple[str, ...]) -> set[str]:
    """Refs from *fields* that resolve to a known entity id (`kind:slug`). Empty,
    tag-like, dict, and non-entity strings are ignored. External `source_refs`
    citations (DOI/PMID/URL/free strings) are absent from `known_ids`, so they are
    excluded automatically."""
    refs: set[str] = set()
    for field in fields:
        value = fm.get(field)
        items = value if isinstance(value, list) else [value] if isinstance(value, str) else []
        for item in items:
            if isinstance(item, str) and item in known_ids:
                refs.add(item)
    return refs


def _shared_anchor_clusters(
    visible: list[tuple[str, str, dict[str, Any]]],
    known_ids: set[str],
    min_cluster_size: int,
) -> list[_RawCluster]:
    """Same-kind entities whose entity-refs (related + resolvable source_refs) point
    at the same anchor entity. Each anchor yields its own raw cluster; when the same
    member-set shares >=2 anchors those clusters merge and the anchor count is what
    lets shared-anchor self-qualify (a single shared anchor is corroborating-only)."""
    anchor_members: dict[tuple[str, str], set[str]] = {}
    for eid, kind, fm in visible:
        for anchor in _entity_refs(fm, known_ids, fields=("related", "source_refs")):
            if anchor == eid:
                continue  # ignore self-reference
            anchor_members.setdefault((kind, anchor), set()).add(eid)

    clusters: list[_RawCluster] = []
    for (kind, anchor), members in anchor_members.items():
        if len(members) < min_cluster_size:
            continue
        clusters.append(
            _RawCluster(
                signal="shared-anchor",
                basis="shared-anchor",
                members=tuple(sorted(members)),
                evidence=f"{len(members)} {kind} entities all ref {anchor}",
            )
        )
    return clusters


def _related_overlap_clusters(
    visible: list[tuple[str, str, dict[str, Any]]],
    known_ids: set[str],
    threshold: float,
    min_cluster_size: int,
) -> list[_RawCluster]:
    """Connected components over entity pairs whose `related:` entity-ref sets have
    Jaccard >= threshold. Kind-agnostic (unlike structural-family / shared-anchor).
    Single-linkage union-find can chain pairwise-similar entities into large blobs;
    the size ceiling in `_merge_gate_order` backstops that pathology."""
    related_sets = {
        eid: _entity_refs(fm, known_ids, fields=("related",)) for eid, _kind, fm in visible
    }
    ids = sorted(eid for eid in related_sets if related_sets[eid])

    parent = {eid: eid for eid in ids}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    best_jaccard: dict[str, float] = {eid: 0.0 for eid in ids}
    for a, b in combinations(ids, 2):
        sa, sb = related_sets[a], related_sets[b]
        union_size = len(sa | sb)
        if union_size == 0:
            continue
        jaccard = len(sa & sb) / union_size
        if jaccard >= threshold:
            union(a, b)
            best_jaccard[a] = max(best_jaccard[a], jaccard)
            best_jaccard[b] = max(best_jaccard[b], jaccard)

    components: dict[str, list[str]] = {}
    for eid in ids:
        components.setdefault(find(eid), []).append(eid)

    clusters: list[_RawCluster] = []
    for members in components.values():
        if len(members) < min_cluster_size:
            continue
        peak = max(best_jaccard[m] for m in members)
        clusters.append(
            _RawCluster(
                signal="related-overlap",
                basis="related-overlap",
                members=tuple(sorted(members)),
                evidence=f"related Jaccard >= {threshold:.2f} (peak {peak:.2f}; {len(members)} members)",
            )
        )
    return clusters


def _merge_gate_order(
    raw: list[_RawCluster],
    *,
    max_cluster_size: int,
) -> tuple[list[SemanticCluster], int]:
    """Merge raw clusters with identical member-sets, gate to genuine candidates,
    and order the survivors.

    A merged cluster qualifies iff it carries a primary basis (id-stem / group /
    related-overlap) OR shares >=2 distinct anchors; task-family-only and
    single-shared-anchor-only clusters are dropped. Qualifying clusters larger than
    *max_cluster_size* are suppressed but counted (no silent caps). id-stem-bearing
    clusters sort first (the redundancy signal worth a human's first look)."""
    by_members: dict[tuple[str, ...], list[_RawCluster]] = {}
    for cluster in raw:
        by_members.setdefault(cluster.members, []).append(cluster)

    ordered_clusters: list[tuple[bool, SemanticCluster]] = []
    suppressed_oversized = 0
    for members, group in by_members.items():
        bases = {c.basis for c in group}
        anchor_count = sum(1 for c in group if c.basis == "shared-anchor")
        if not (bases & _PRIMARY_BASES or anchor_count >= 2):
            continue
        if len(members) > max_cluster_size:
            suppressed_oversized += 1
            continue
        ordered = sorted(group, key=lambda c: (c.signal, c.evidence))
        signal = "+".join(sorted({c.signal for c in group}))
        evidence = " | ".join(c.evidence for c in ordered)
        has_id_stem = "id-stem" in bases
        ordered_clusters.append(
            (has_id_stem, SemanticCluster(signal=signal, members=list(members), evidence=evidence))
        )

    ordered_clusters.sort(key=lambda t: (not t[0], t[1].signal, t[1].members))
    return [c for _has_id_stem, c in ordered_clusters], suppressed_oversized


def _lineage_section(graph: SupersedesGraph) -> SupersededLineage:
    linear = [
        LinearChain(
            survivor=chain.survivor,
            archivable=list(chain.superseded),
            members=sorted([chain.survivor, *chain.superseded]),
        )
        for chain in graph.linear
    ]
    non_linear = [NonLinearChain(nodes=list(comp.nodes), reason=comp.reason) for comp in graph.non_linear]
    return SupersededLineage(linear=linear, non_linear=non_linear)


def detect_consolidation_candidates(
    project_root: Path,
    *,
    related_jaccard: float = 0.7,
    min_cluster_size: int = 2,
    max_cluster_size: int = 15,
) -> ConsolidationCandidates:
    """Detect consolidation candidates under ``project_root`` (read-only).

    Lineage is reported unfiltered (regardless of visibility or kind capability);
    semantic clustering considers default-visible entities only, gates to genuine
    redundancy candidates, and suppresses (but counts) clusters larger than
    *max_cluster_size*.
    """
    project_root = Path(project_root).resolve()
    entries = iter_entity_frontmatter(project_root)
    graph = build_supersedes_graph(entries)
    lineage = _lineage_section(graph)

    visible: list[tuple[str, str, dict[str, Any]]] = [
        (str(fm["id"]), graph.kind_by_id[str(fm["id"])], fm)
        for _path, fm in entries
        if is_default_visible(graph.status_by_id.get(str(fm["id"])))
    ]
    known_ids = set(graph.kind_by_id)
    raw_clusters = _structural_family_clusters(visible, min_cluster_size)
    raw_clusters += _shared_anchor_clusters(visible, known_ids, min_cluster_size)
    raw_clusters += _related_overlap_clusters(visible, known_ids, related_jaccard, min_cluster_size)
    semantic, suppressed_oversized = _merge_gate_order(raw_clusters, max_cluster_size=max_cluster_size)

    counts = {
        "linear": len(lineage.linear),
        "non_linear": len(lineage.non_linear),
        "semantic": len(semantic),
        "suppressed_oversized": suppressed_oversized,
    }
    return ConsolidationCandidates(
        project_root=str(project_root),
        superseded_lineage=lineage,
        semantic_clusters=semantic,
        counts=counts,
    )


def render_text(report: ConsolidationCandidates) -> str:
    """Deterministic plain-text rendering of a candidates report."""
    lines = [
        f"Consolidation candidates for {report.project_root}",
        f"  superseded lineage: {report.counts['linear']} linear, {report.counts['non_linear']} non-linear",
        f"  semantic clusters:  {report.counts['semantic']} "
        f"({report.counts['suppressed_oversized']} oversized suppressed)",
    ]
    for chain in report.superseded_lineage.linear:
        lines.append(f"  [linear] survivor {chain.survivor}; archivable {', '.join(chain.archivable)}")
    for comp in report.superseded_lineage.non_linear:
        lines.append(f"  [non-linear] {', '.join(comp.nodes)} — {comp.reason}")
    for cluster in report.semantic_clusters:
        lines.append(f"  [{cluster.signal}] {', '.join(cluster.members)} — {cluster.evidence}")
    return "\n".join(lines)
