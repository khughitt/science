"""Weighted attention sampling over epistemic graph entities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import SKOS

from science_tool.entities import CLOSED_LIFECYCLE_STATUSES, valid_statuses
from science_tool.graph.belief import aggregate_belief, collect_evidence_units
from science_tool.graph.belief_scalar import belief_scalar, belief_scalar_enabled, format_belief_weight
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS, project_root_from_graph_path
from science_tool.graph.store import _evidence_targets_for_uri, _graph_uri, canonical_id_from_entity_uri
from science_tool.instruments import InstrumentResult

DEFAULT_EPSILON = 0.05
NEEDS_REVIEW_MULTIPLIER = 3.0
STALE_MULTIPLIER = 2.0
NEVER_REVIEWED_DAYS = 365.0
OPEN_QUESTION_DEBT_WEIGHT = 0.5
# Canonical question debt statuses (science_model entities.py); resolved
# states (answered/retired) are deliberately excluded — they are not debt.
DEBT_QUESTION_STATUSES = frozenset({"active", "partially-answered", "deferred"})

#: The single precondition of the attention instrument. Candidacy is gated on
#: ``sci:freshnessState``; with no such triple in ``graph/knowledge``, NO entity has
#: been assessed for attention and the ranking is not a ranking of anything.
FRESHNESS_STATE_ABSENT = "freshness_state_absent"
_FRESHNESS_STATE_ABSENT_REASON = (
    "graph/knowledge carries no sci:freshnessState triples — the freshness pass has not run "
    "(or the layer is missing from this graph), so no entity has been assessed for attention. "
    "Run `science graph build` to emit freshness state."
)


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
) -> InstrumentResult[AttentionCandidate]:
    """Compute attention weights for epistemic entities in a materialized graph.

    Candidates are entities carrying ``sci:freshnessState``. That keeps the
    surface tied to Phase 1's epistemic freshness emission and avoids guessing
    classification from labels or LLM judgement.

    That single predicate is also the instrument's single precondition. ``Dataset.graph()``
    CREATES an empty graph when ``graph/knowledge`` is absent, so a graph missing the layer
    and a project whose freshness pass never ran both look like "zero candidates" — which
    would be rendered as "nothing deserves attention". They are ``unwired`` instead.
    A ``kinds`` filter that selects none of the freshness-bearing entities is NOT unwired:
    the instrument ran, and zero is the honest answer to what the caller asked.
    """
    if epsilon <= 0:
        raise ValueError("epsilon must be > 0")

    current_date = today or date.today()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    state_triples = sorted(knowledge.triples((None, SCI_NS.freshnessState, None)), key=str)
    if not state_triples:
        return InstrumentResult.unwired(
            code=FRESHNESS_STATE_ABSENT,
            reason=_FRESHNESS_STATE_ABSENT_REASON,
        )

    candidates: list[AttentionCandidate] = []

    for entity_uri, _, state_literal in state_triples:
        if not isinstance(entity_uri, URIRef):
            continue
        entity_id = canonical_id_from_entity_uri(str(entity_uri))
        if entity_id is None:
            continue
        kind, _, _ = entity_id.partition(":")
        if kinds is not None and kind not in kinds:
            continue

        # A TERMINAL entity is not a work item, so it is not ranked.
        #
        # This is not cosmetic. Every term that drives the weight below is HIGHEST for a
        # hypothesis that just died: it accumulated the most incoming bears_on and the most
        # open questions precisely BECAUSE it was the organizing frame. natural-systems'
        # refuted hypothesis:0009 led its ranking on open_question_debt=10 and 27 incoming
        # bears_on -- so being disproved made it MORE attention-worthy, and the system
        # recommended working hardest on the thing it believed least (fb-2026-07-11-005).
        #
        # It stays in the graph: queryable, provenance-visible, lineage intact. Closure is
        # not hiding. Its orphaned questions do not vanish with it -- see `list_rehoming_debt`.
        #
        # CLOSURE IS READ OFF THE LIFECYCLE, not off a verdict. A `refuted` hypothesis that is still
        # being written up is `status: active` and STAYS RANKED -- it is live work. What drops out is
        # a hypothesis somebody CLOSED. Reading terminality off the verdict instead would re-collapse
        # the two axes and silently unrank every hypothesis the evidence went against, whether or not
        # anyone was done with it.
        if _is_closed(knowledge, entity_uri):
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
    return InstrumentResult.from_rows(candidates)


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
) -> InstrumentResult[dict[str, Any]]:
    """Load a materialized graph and return sampled attention rows.

    Propagates an ``unwired`` candidate set rather than sampling it: a sample drawn from
    an instrument that never ran is not a sample, and an empty one would read as "these
    are the entities that came up".
    """
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    candidates = compute_attention_candidates(dataset, today=today, kinds=kinds, epsilon=epsilon)
    if candidates.status == "unwired":
        return InstrumentResult.unwired(
            code=candidates.code or FRESHNESS_STATE_ABSENT, reason=candidates.reason
        )
    if reason_aware:
        sample = reason_aware_sample_candidates(candidates.rows, limit=limit, seed=seed)
    else:
        sample = weighted_sample_without_replacement(candidates.rows, limit=limit, seed=seed)
    return InstrumentResult.from_rows(
        _rows_with_belief(graph_path, dataset, sample), code=candidates.code, reason=candidates.reason
    )


def query_attention_ranked(
    graph_path: Path,
    *,
    limit: int | None = None,
    today: date | None = None,
    kinds: set[str] | None = None,
    epsilon: float = DEFAULT_EPSILON,
) -> InstrumentResult[dict[str, Any]]:
    """Load a materialized graph and return all candidates ranked by weight desc.

    Deterministic (no sampling): ties break by entity_id. This is the review-queue
    surface — `graph attention-rank` — distinct from the weighted-random
    `attention-sample`. An ``unwired`` candidate set propagates: an empty review queue
    over an unassessed graph would say "nothing needs review".
    """
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    candidates = compute_attention_candidates(dataset, today=today, kinds=kinds, epsilon=epsilon)
    if candidates.status == "unwired":
        return InstrumentResult.unwired(
            code=candidates.code or FRESHNESS_STATE_ABSENT, reason=candidates.reason
        )
    ranked = sorted(candidates.rows, key=lambda candidate: (-candidate.weight, candidate.entity_id))
    if limit is not None:
        ranked = ranked[:limit]
    return InstrumentResult.from_rows(
        _rows_with_belief(graph_path, dataset, ranked), code=candidates.code, reason=candidates.reason
    )


def _rows_with_belief(
    graph_path: Path, dataset: Dataset, candidates: Sequence[AttentionCandidate]
) -> list[dict[str, Any]]:
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

    return [format_attention_candidate(c, belief_weight=_belief_weight(c)) for c in candidates]


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


def _is_closed(knowledge, entity_uri: URIRef) -> bool:
    """Is this entity CLOSED — no longer an object of active work?

    Off the LIFECYCLE (`sci:projectStatus`), against the one vocabulary in `entities.py`. This
    replaces `sci:disposition`, which said the same thing in a second field that no file ever
    authored.
    """
    status = next(knowledge.objects(entity_uri, SCI_NS.projectStatus), None)
    return status is not None and str(status) in CLOSED_LIFECYCLE_STATUSES


def _unmigrated_hypotheses(knowledge) -> list[str]:
    """Hypotheses whose `status` is not a word the lifecycle vocabulary knows.

    THE WIRING QUESTION, and it has to be asked before any terminality claim. Before this arc a
    hypothesis' `status` held the epistemic VERDICT (`proposed`, `supported`, `refuted`, ...), and
    not one of those words is a lifecycle state. So on an unmigrated project every hypothesis looks
    non-terminal, and the honest report is "I cannot tell" -- not a confident zero.

    That distinction is the whole point of `InstrumentResult.unwired`: a project's hypotheses cannot
    be said to carry "no re-homing debt" by an instrument that cannot read their lifecycle at all.
    """
    lifecycle = valid_statuses("hypothesis") or frozenset()
    return sorted(
        f"{canonical_id_from_entity_uri(str(subject))} (status: {status})"
        for subject, _, status in knowledge.triples((None, SCI_NS.projectStatus, None))
        if _entity_kind_of(subject) == "hypothesis" and str(status) not in lifecycle
    )


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


def list_rehoming_debt(graph_path: Path) -> InstrumentResult[dict[str, str]]:
    """Debt-status questions still resolving to a TERMINAL hypothesis.

    Closing a hypothesis does NOT close its questions -- it UNHOUSES them. natural-systems'
    refuted hypothesis:0009 still carried 10 open questions; they did not become
    uninteresting because their frame died, they became homeless.

    This exists because the attention exclusion is dangerous on its own. Dropping a terminal
    hypothesis from the ranking also drops its questions' debt from view, which would convert
    a VISIBLE debt into an INVISIBLE one -- strictly worse than the bug being fixed
    (fb-2026-07-11-005). Retirement CREATES work, and the system must show it.

    The dead hypothesis is not ranked. Its re-homing debt is.

    `unwired` when the project's hypotheses do not speak the lifecycle vocabulary yet -- their
    `status` still holds the epistemic VERDICT, so terminality is not a question this instrument can
    answer about them, and a zero would not mean "no debt". It would mean "I cannot read this
    project."
    """
    dataset = Dataset()
    dataset.parse(source=str(graph_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    unmigrated = _unmigrated_hypotheses(knowledge)
    if unmigrated:
        return InstrumentResult.unwired(
            code="hypothesis_lifecycle_unmigrated",
            reason=(
                "these hypotheses carry a `status` outside the lifecycle vocabulary, so their "
                "closure cannot be read: "
                f"{', '.join(unmigrated)}. Migrate the project (`science entity migrate-status`) "
                "-- zero re-homing debt here would not mean 'no debt', it would mean 'unreadable'."
            ),
        )

    rows: list[dict[str, str]] = []
    terminal_uris = sorted(
        (
            subject
            for subject in knowledge.subjects(SCI_NS.projectStatus, None)
            if isinstance(subject, URIRef)
            and _entity_kind_of(subject) == "hypothesis"
            and _is_closed(knowledge, subject)
        ),
        key=str,
    )
    for hypothesis_uri in terminal_uris:
        hypothesis_id = canonical_id_from_entity_uri(str(hypothesis_uri))
        if hypothesis_id is None:
            continue

        for question_uri in sorted(_related_neighbors(knowledge, hypothesis_uri), key=str):
            if _entity_kind_of(question_uri) != "question":
                continue
            status_literal = next(knowledge.objects(question_uri, SCI_NS.projectStatus), None)
            if status_literal is None or str(status_literal) not in DEBT_QUESTION_STATUSES:
                continue
            question_id = canonical_id_from_entity_uri(str(question_uri))
            if question_id is None:
                continue
            rows.append(
                {
                    "question": question_id,
                    "terminal_hypothesis": hypothesis_id,
                    "question_status": str(status_literal),
                }
            )

    return InstrumentResult.from_rows(rows)


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
