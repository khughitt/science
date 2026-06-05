"""Weighted attention sampling over epistemic graph entities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import SKOS

from science_tool.graph.belief import aggregate_belief, collect_evidence_units
from science_tool.graph.belief_scalar import belief_scalar, belief_scalar_enabled, format_belief_weight
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS, project_root_from_graph_path
from science_tool.graph.store import _evidence_targets_for_uri, _graph_uri, canonical_id_from_entity_uri

DEFAULT_EPSILON = 0.05
NEEDS_REVIEW_MULTIPLIER = 3.0
STALE_MULTIPLIER = 2.0
NEVER_REVIEWED_DAYS = 365.0
OPEN_QUESTION_DEBT_WEIGHT = 0.5
# Canonical question debt statuses (science_model entities.py); resolved
# states (answered/retired) are deliberately excluded — they are not debt.
DEBT_QUESTION_STATUSES = frozenset({"active", "partially-answered", "deferred"})


@dataclass(frozen=True)
class AttentionReason:
    """Machine-visible reason metadata for why an entity deserves attention."""

    code: str
    direction: str
    strength: str
    provenance: str
    next_action: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "direction": self.direction,
            "strength": self.strength,
            "provenance": self.provenance,
            "next_action": self.next_action,
        }

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, AttentionReason):
            return self.as_dict() == other.as_dict()
        if isinstance(other, Mapping):
            return self.as_dict() == other
        return NotImplemented


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
    reasons: Sequence[AttentionReason]


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
        evidence_source_count = support_count + dispute_count
        evidence_balance_factor = _evidence_balance_factor(support_count, dispute_count)
        freshness_multiplier = _freshness_multiplier(freshness_state)
        open_question_debt = _open_question_debt(knowledge, entity_uri)

        weight = (
            (1.0 + incoming_bears_on)
            * (1.0 + (days_since_last_review / 30.0))
            * freshness_multiplier
            * evidence_balance_factor
            * (1.0 + OPEN_QUESTION_DEBT_WEIGHT * open_question_debt)
        ) + epsilon

        reasons = list(_derive_phase1_reasons(kind, support_count, dispute_count))
        if open_question_debt > 0:
            reasons.append(_open_question_debt_reason(open_question_debt))

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
                    "evidence_source_count": float(evidence_source_count),
                    "evidence_balance_factor": float(evidence_balance_factor),
                    "open_question_debt": float(open_question_debt),
                    "epsilon": float(epsilon),
                },
                reasons=reasons,
            )
        )

    candidates.sort(key=lambda candidate: candidate.entity_id)
    return candidates


def reason_aware_sample_candidates(
    candidates: Sequence[AttentionCandidate],
    *,
    limit: int,
    seed: int | None = None,
) -> list[AttentionCandidate]:
    """Sample candidates with a bounded reason-coded review slice.

    This is a review-routing toggle, not a replacement belief model. It promotes
    ordinary uncertainty reasons first, then fills the rest using the existing
    weighted sampler so the epsilon floor remains meaningful.
    """
    if limit < 0:
        raise ValueError("limit must be >= 0")
    if limit == 0 or not candidates:
        return []

    promoted = [candidate for candidate in candidates if _is_uncertainty_review_candidate(candidate)]
    promoted = sorted(promoted, key=_reason_route_sort_key)
    promoted_limit = min(len(promoted), max(1, limit // 2))
    review_slice = promoted[:promoted_limit]

    remaining_limit = limit - len(review_slice)
    if remaining_limit == 0:
        return review_slice

    selected_ids = {candidate.entity_id for candidate in review_slice}
    tail_pool = [candidate for candidate in candidates if candidate.entity_id not in selected_ids]
    return review_slice + weighted_sample_without_replacement(tail_pool, limit=remaining_limit, seed=seed)


def _is_uncertainty_review_candidate(candidate: AttentionCandidate) -> bool:
    codes = {reason.code for reason in candidate.reasons}
    if "strong_counterevidence" in codes or "unscaffolded" in codes:
        return False
    return bool(codes & {"contestation", "fragility"})


def _reason_route_sort_key(candidate: AttentionCandidate) -> tuple[int, float, str]:
    codes = {reason.code for reason in candidate.reasons}
    if "contestation" in codes:
        bucket = 0
    elif "fragility" in codes:
        bucket = 1
    else:
        bucket = 2
    return (bucket, -candidate.weight, candidate.entity_id)


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
    reason_aware: bool = False,
) -> list[dict[str, Any]]:
    """Load a materialized graph and return sampled attention rows."""
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    candidates = compute_attention_candidates(dataset, today=today, kinds=kinds, epsilon=epsilon)
    if reason_aware:
        sample = reason_aware_sample_candidates(candidates, limit=limit, seed=seed)
    else:
        sample = weighted_sample_without_replacement(candidates, limit=limit, seed=seed)

    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    enabled = belief_scalar_enabled(project_root_from_graph_path(graph_path))

    def _belief_weight(candidate: AttentionCandidate) -> dict[str, Any] | None:
        if not enabled:
            return None
        units = collect_evidence_units(
            knowledge, provenance, _evidence_targets_for_uri(knowledge, URIRef(candidate.uri))
        )
        result = aggregate_belief(units)
        return format_belief_weight(result, belief_scalar(result))

    return [format_attention_candidate(c, belief_weight=_belief_weight(c)) for c in sample]


def format_attention_candidate(
    candidate: AttentionCandidate, belief_weight: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Format a candidate for CLI table / JSON output."""
    components = candidate.components
    return {
        "id": candidate.entity_id,
        "kind": candidate.kind,
        "label": candidate.label,
        "freshness_state": candidate.freshness_state,
        "attention_weight": f"{candidate.weight:.4f}",
        "belief_weight": belief_weight,
        "influence_weight": None,
        "incoming_bears_on": str(int(components["incoming_bears_on"])),
        "days_since_last_review": f"{components['days_since_last_review']:.0f}",
        "support_count": str(int(components["support_count"])),
        "dispute_count": str(int(components["dispute_count"])),
        "evidence_source_count": str(int(components["evidence_source_count"])),
        "evidence_balance_factor": f"{components['evidence_balance_factor']:.2f}",
        "open_question_debt": str(int(components["open_question_debt"])),
        "reasons": [reason.as_dict() for reason in candidate.reasons],
    }


def _open_question_debt_reason(debt: int) -> AttentionReason:
    if debt >= 3:
        strength = "high"
    elif debt == 2:
        strength = "moderate"
    else:
        strength = "low"
    return AttentionReason(
        code="open_question_debt",
        direction="increase_attention",
        strength=strength,
        provenance=f"derived:open_question_debt(related+theme,{debt})",
        next_action="incorporate_or_answer_open_questions",
    )


def _derive_phase1_reasons(kind: str, support_count: int, dispute_count: int) -> list[AttentionReason]:
    if kind != "proposition":
        return []

    evidence_source_count = support_count + dispute_count
    reasons: list[AttentionReason] = []

    if evidence_source_count == 0:
        reasons.append(
            AttentionReason(
                code="unscaffolded",
                direction="route_attention",
                strength="high",
                provenance="derived:unscaffolded_source_count(evidence_source_count)",
                next_action="scaffold_evidence_base",
            )
        )
        return reasons

    if evidence_source_count <= 2:
        reasons.append(
            AttentionReason(
                code="fragility",
                direction="increase_attention",
                strength="high" if evidence_source_count == 1 else "moderate",
                provenance="derived:fragility_source_count(evidence_source_count)",
                next_action="seek_independent_evidence",
            )
        )

    if support_count >= 1 and dispute_count >= 1:
        reasons.append(
            AttentionReason(
                code="contestation",
                direction="increase_attention",
                strength=_contestation_strength(support_count, dispute_count),
                provenance="derived:contestation_counts(support_count,dispute_count)",
                next_action="compare_contexts",
            )
        )

    if _has_strong_counterevidence(support_count, dispute_count):
        reasons.append(
            AttentionReason(
                code="strong_counterevidence",
                direction="decrease_attention",
                strength=_counterevidence_strength(support_count, dispute_count),
                provenance="derived:counterevidence_counts(support_count,dispute_count)",
                next_action="preserve_floor",
            )
        )

    return reasons


def _contestation_strength(support_count: int, dispute_count: int) -> str:
    weaker_count = min(support_count, dispute_count)
    stronger_count = max(support_count, dispute_count)
    if weaker_count >= 2:
        return "high"
    if stronger_count < weaker_count * 3:
        return "moderate"
    return "low"


def _has_strong_counterevidence(support_count: int, dispute_count: int) -> bool:
    if dispute_count >= 1 and support_count == 0:
        return True
    return dispute_count >= 2 * max(support_count, 1) and dispute_count >= 2


def _counterevidence_strength(support_count: int, dispute_count: int) -> str:
    if support_count == 0 and dispute_count >= 3:
        return "high"
    if support_count > 0 and dispute_count / support_count >= 3:
        return "high"
    return "moderate"


def _count_uri_objects(triples: Iterable[tuple[object, object, object]]) -> int:
    count = 0
    for _s, _p, obj in triples:
        if isinstance(obj, URIRef):
            count += 1
    return count


def _entity_kind_of(uri: URIRef) -> str | None:
    canonical_id = canonical_id_from_entity_uri(str(uri))
    if canonical_id is None:
        return None
    return canonical_id.partition(":")[0]


def _related_neighbors(knowledge, uri: URIRef) -> set[URIRef]:
    """All entities joined to ``uri`` by a skos:related edge, either direction.

    `related:` is materialized subject=authoring-entity (materialize.py:353), so a
    question that lists an entity in its `related:` shows up as an *incoming* edge.
    """
    neighbors: set[URIRef] = set()
    for obj in knowledge.objects(uri, SKOS.related):
        if isinstance(obj, URIRef):
            neighbors.add(obj)
    for subj in knowledge.subjects(SKOS.related, uri):
        if isinstance(subj, URIRef):
            neighbors.add(subj)
    return neighbors


def _open_question_debt(knowledge, entity_uri: URIRef) -> int:
    """Count debt-status questions bearing on ``entity_uri`` via the connectivity
    layer freshness ignores: direct skos:related (either direction) plus theme
    co-membership (entity and question both related to the same theme node).

    Intentionally does NOT use bears_on: scoping questions sit on related: edges
    or weaker, which never become bears_on (freshness.py:70), so a bears_on-based
    metric would inherit the exact blind spot this term exists to cover. Question
    age is not weighted here because created/updated are not emitted as graph
    triples (see plan grounding facts); age weighting is deferred past M1.
    """
    neighbors = _related_neighbors(knowledge, entity_uri)
    question_uris: set[URIRef] = set()
    for neighbor in neighbors:
        kind = _entity_kind_of(neighbor)
        if kind == "question":
            question_uris.add(neighbor)
        elif kind == "theme":
            for theme_neighbor in _related_neighbors(knowledge, neighbor):
                if _entity_kind_of(theme_neighbor) == "question":
                    question_uris.add(theme_neighbor)

    # A question is itself an attention candidate (it carries freshnessState) and a
    # question→theme edge makes the question a theme co-member of itself. Never let
    # an entity count itself as its own debt.
    question_uris.discard(entity_uri)

    debt = 0
    for question_uri in question_uris:
        status_literal = next(knowledge.objects(question_uri, SCI_NS.projectStatus), None)
        if status_literal is not None and str(status_literal) in DEBT_QUESTION_STATUSES:
            debt += 1
    return debt


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
