"""Projection for `science curate consolidation-candidates` display. Caps the three
growable lists and records how many rows were dropped, without touching `counts`."""

from __future__ import annotations

from typing import Any

CONSOLIDATION_ROW_CAP = 40


def project_consolidation_candidates(payload: dict[str, Any], cap: int = CONSOLIDATION_ROW_CAP) -> dict[str, Any]:
    if cap < 0:
        raise ValueError(f"consolidation cap must be non-negative, got {cap}")
    lineage = payload.get("superseded_lineage") or {}
    linear = lineage.get("linear") or []
    non_linear = lineage.get("non_linear") or []
    clusters = payload.get("semantic_clusters") or []

    capped_linear = linear[:cap]
    capped_non_linear = non_linear[:cap]
    capped_clusters = clusters[:cap]
    omitted = (
        (len(linear) - len(capped_linear))
        + (len(non_linear) - len(capped_non_linear))
        + (len(clusters) - len(capped_clusters))
    )
    return {
        **payload,
        "superseded_lineage": {**lineage, "linear": capped_linear, "non_linear": capped_non_linear},
        "semantic_clusters": capped_clusters,
        "candidates_omitted": omitted,
    }
