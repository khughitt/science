from __future__ import annotations

from pathlib import Path

from science_tool.graph.attention import (
    AttentionCandidate,
    compute_attention_candidates,
    weighted_sample_without_replacement,
)
from science_tool.graph.trig import load_trig_dataset_preserving_literals


class WanderSamplerError(Exception):
    """Raised when a wander sample cannot be drawn."""


def sample_for_walk(
    *,
    graph_path: Path,
    n: int,
    seed: int | None,
    kinds: set[str] | None = None,
    epsilon: float = 0.05,
) -> list[AttentionCandidate]:
    """Draw `n` epistemic entities from the materialized graph.

    Wraps the existing attention machinery but preserves URI and raw
    weight components for downstream context-bundle assembly.

    Raises ``WanderSamplerError`` when the attention instrument could not run (no
    ``sci:freshnessState`` in the graph). Returning an empty walk there would present
    an unassessed graph as one with nothing worth wandering to.
    """
    if not graph_path.exists():
        raise WanderSamplerError(f"Graph file not found at {graph_path}. Run `science graph build` first.")

    dataset = load_trig_dataset_preserving_literals(graph_path)
    candidates = compute_attention_candidates(dataset, kinds=kinds, epsilon=epsilon)
    if candidates.status == "unwired":
        raise WanderSamplerError(f"Attention sampling did not run ({candidates.code}): {candidates.reason}")
    return weighted_sample_without_replacement(candidates.rows, limit=n, seed=seed)
