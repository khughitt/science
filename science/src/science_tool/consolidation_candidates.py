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
    archivable: list[str]  # the superseded tail (everything but the survivor)
    members: list[str]     # all nodes including the survivor, sorted


class NonLinearChain(BaseModel):
    nodes: list[str]
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

    semantic: list[SemanticCluster] = []  # populated in Tasks 3-7

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
