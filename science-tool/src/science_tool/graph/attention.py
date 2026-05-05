"""Weighted attention sampling over epistemic graph entities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import SKOS

from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store import canonical_id_from_entity_uri

DEFAULT_EPSILON = 0.05
NEEDS_REVIEW_MULTIPLIER = 3.0
STALE_MULTIPLIER = 2.0
NEVER_REVIEWED_DAYS = 365.0


@dataclass(frozen=True)
class AttentionCandidate:
    """One graph entity with an observable attention weight."""

    entity_id: str
    uri: str
    kind: str
    label: str
    freshness_state: str
    weight: float
    components: Mapping[str, float]


def compute_attention_candidates(
    dataset: Dataset,
    *,
    today: date | None = None,
    kinds: set[str] | None = None,
    epsilon: float = DEFAULT_EPSILON,
) -> list[AttentionCandidate]:
    """Compute attention weights for epistemic entities in a materialized graph.

    Candidates are entities carrying ``sci:freshnessState``. That keeps the
    surface tied to Phase 1's epistemic freshness emission and avoids guessing
    classification from labels or LLM judgement.
    """
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")

    current_date = today or date.today()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    candidates: list[AttentionCandidate] = []

    for entity_uri, _, state_literal in sorted(knowledge.triples((None, SCI_NS.freshnessState, None)), key=str):
        if not isinstance(entity_uri, URIRef):
            continue
        entity_id = canonical_id_from_entity_uri(str(entity_uri))
        if entity_id is None:
            continue
        kind, _, _ = entity_id.partition(":")
        if kinds is not None and kind not in kinds:
            continue

        freshness_state = str(state_literal)
        incoming_bears_on = _count_uri_objects(knowledge.triples((None, SCI_NS.bearsOn, entity_uri)))
        days_since_last_review = _days_since_last_review(knowledge, entity_uri, current_date)
        support_count = _count_uri_objects(knowledge.triples((None, CITO_NS.supports, entity_uri)))
        dispute_count = _count_uri_objects(knowledge.triples((None, CITO_NS.disputes, entity_uri)))
        evidence_balance_factor = _evidence_balance_factor(support_count, dispute_count)
        freshness_multiplier = _freshness_multiplier(freshness_state)

        weight = (
            (1.0 + incoming_bears_on)
            * (1.0 + (days_since_last_review / 30.0))
            * freshness_multiplier
            * evidence_balance_factor
        ) + epsilon

        candidates.append(
            AttentionCandidate(
                entity_id=entity_id,
                uri=str(entity_uri),
                kind=kind,
                label=_label_for(knowledge, entity_uri, entity_id),
                freshness_state=freshness_state,
                weight=weight,
                components={
                    "incoming_bears_on": float(incoming_bears_on),
                    "days_since_last_review": float(days_since_last_review),
                    "freshness_multiplier": float(freshness_multiplier),
                    "support_count": float(support_count),
                    "dispute_count": float(dispute_count),
                    "evidence_balance_factor": float(evidence_balance_factor),
                    "epsilon": float(epsilon),
                },
            )
        )

    candidates.sort(key=lambda candidate: candidate.entity_id)
    return candidates


def weighted_sample_without_replacement(
    candidates: Sequence[AttentionCandidate],
    *,
    limit: int,
    seed: int | None = None,
) -> list[AttentionCandidate]:
    """Sample candidates by weight without replacement."""
    if limit < 0:
        raise ValueError("limit must be >= 0")
    if limit == 0 or not candidates:
        return []

    rng = random.Random(seed)
    remaining = list(candidates)
    sample: list[AttentionCandidate] = []
    draw_count = min(limit, len(remaining))

    for _ in range(draw_count):
        total_weight = sum(candidate.weight for candidate in remaining)
        if total_weight <= 0:
            raise ValueError("candidate weights must sum to a positive value")
        threshold = rng.random() * total_weight
        running = 0.0
        for index, candidate in enumerate(remaining):
            running += candidate.weight
            if running >= threshold:
                sample.append(candidate)
                del remaining[index]
                break
        else:
            sample.append(remaining.pop())

    return sample


def query_attention_sample(
    graph_path: Path,
    *,
    limit: int,
    seed: int | None = None,
    today: date | None = None,
    kinds: set[str] | None = None,
    epsilon: float = DEFAULT_EPSILON,
) -> list[dict[str, str]]:
    """Load a materialized graph and return sampled attention rows."""
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    candidates = compute_attention_candidates(dataset, today=today, kinds=kinds, epsilon=epsilon)
    sample = weighted_sample_without_replacement(candidates, limit=limit, seed=seed)
    return [format_attention_candidate(candidate) for candidate in sample]


def format_attention_candidate(candidate: AttentionCandidate) -> dict[str, str]:
    """Format a candidate for CLI table / JSON output."""
    components = candidate.components
    return {
        "id": candidate.entity_id,
        "kind": candidate.kind,
        "label": candidate.label,
        "freshness_state": candidate.freshness_state,
        "attention_weight": f"{candidate.weight:.4f}",
        "incoming_bears_on": str(int(components["incoming_bears_on"])),
        "days_since_last_review": f"{components['days_since_last_review']:.0f}",
        "support_count": str(int(components["support_count"])),
        "dispute_count": str(int(components["dispute_count"])),
        "evidence_balance_factor": f"{components['evidence_balance_factor']:.2f}",
    }


def _count_uri_objects(triples: Iterable[tuple[object, object, object]]) -> int:
    count = 0
    for _s, _p, obj in triples:
        if isinstance(obj, URIRef):
            count += 1
    return count


def _days_since_last_review(knowledge, entity_uri: URIRef, today: date) -> float:
    literal = next(knowledge.objects(entity_uri, SCI_NS.lastReviewed), None)
    if literal is None:
        return NEVER_REVIEWED_DAYS
    parsed = _parse_date_literal(literal)
    if parsed is None:
        return NEVER_REVIEWED_DAYS
    return float(max((today - parsed).days, 0))


def _parse_date_literal(value: object) -> date | None:
    text = str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _freshness_multiplier(state: str) -> float:
    if state == "needs-review":
        return NEEDS_REVIEW_MULTIPLIER
    if state == "stale":
        return STALE_MULTIPLIER
    return 1.0


def _evidence_balance_factor(support_count: int, dispute_count: int) -> float:
    total = support_count + dispute_count
    if total == 0:
        return 1.0
    skew = abs(support_count - dispute_count) / total
    return 1.0 + (1.0 - skew)


def _label_for(knowledge, entity_uri: URIRef, fallback: str) -> str:
    label = next(knowledge.objects(entity_uri, SKOS.prefLabel), None)
    if isinstance(label, Literal) and str(label).strip():
        return str(label)
    return fallback
