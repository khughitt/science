"""Read-only consolidation-candidate detector (P2).

Scans canonical ``entities/`` and reports two kinds of consolidation candidates —
superseded-lineage (mechanical) and semantic clusters (dep-free heuristics) —
each with surfaced evidence. Takes NO action. This is the decision-support
surface for the future ``entities consolidate --apply``. See
docs/plans/2026-06-15-entity-consolidation-p2-candidate-detector-design.md.
"""

from __future__ import annotations

import re
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
) -> list[SemanticCluster]:
    """Basis-namespaced structural grouping. Keys are (kind, basis, value) so the
    three sub-bases never collide by value; identical member-sets merge later."""
    groups: dict[tuple[str, str, str], list[str]] = {}
    for eid, kind, _fm in visible:
        groups.setdefault((kind, "id-stem", _id_stem(eid)), []).append(eid)
        group_value = _fm.get("group")
        if isinstance(group_value, str) and group_value:
            groups.setdefault((kind, "group", group_value), []).append(eid)
        for task_ref in _task_refs(_fm):
            groups.setdefault((kind, "task-family", task_ref), []).append(eid)

    clusters: list[SemanticCluster] = []
    for (kind, basis, value), members in groups.items():
        if len(members) < min_cluster_size:
            continue
        clusters.append(
            SemanticCluster(
                signal="structural-family",
                members=sorted(members),
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
) -> list[SemanticCluster]:
    """Same-kind entities whose entity-refs (related + resolvable source_refs) point
    at the same anchor entity."""
    anchor_members: dict[tuple[str, str], set[str]] = {}
    for eid, kind, fm in visible:
        for anchor in _entity_refs(fm, known_ids, fields=("related", "source_refs")):
            if anchor == eid:
                continue  # ignore self-reference
            anchor_members.setdefault((kind, anchor), set()).add(eid)

    clusters: list[SemanticCluster] = []
    for (kind, anchor), members in anchor_members.items():
        if len(members) < min_cluster_size:
            continue
        clusters.append(
            SemanticCluster(
                signal="shared-anchor",
                members=sorted(members),
                evidence=f"{len(members)} {kind} entities all ref {anchor}",
            )
        )
    return clusters


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
    related_jaccard: float = 0.5,
    min_cluster_size: int = 2,
) -> ConsolidationCandidates:
    """Detect consolidation candidates under ``project_root`` (read-only).

    Lineage is reported unfiltered (regardless of visibility or kind capability);
    semantic clustering considers default-visible entities only.
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
    semantic = _structural_family_clusters(visible, min_cluster_size)
    semantic += _shared_anchor_clusters(visible, known_ids, min_cluster_size)

    counts = {
        "linear": len(lineage.linear),
        "non_linear": len(lineage.non_linear),
        "semantic": len(semantic),
    }
    return ConsolidationCandidates(
        project_root=str(project_root),
        superseded_lineage=lineage,
        semantic_clusters=semantic,
        counts=counts,
    )
