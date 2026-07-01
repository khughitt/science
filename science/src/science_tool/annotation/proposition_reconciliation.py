from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from science_model.reasoning import SIGN_MEANINGFUL_PREDICATES


Priority = Literal["high", "medium", "low"]
LANE_SAME_CLAIM = "same_claim"
LANE_FACTORIZATION = "factorization_disagreement"
MAX_RECONCILIATION_COMPONENT_SIZE = 25
LANE_ID_TOKENS = {
    LANE_SAME_CLAIM: "same-claim",
    LANE_FACTORIZATION: "factorization",
}

DECISIONS = frozenset(
    {
        "same_claim",
        "related_but_distinct",
        "conflict_or_negation",
        "factorization_needs_resynthesis",
        "stance_review_needed",
        "split_possible",
        "insufficient_hints",
        "needs_human",
    }
)
LANE_B_DECISIONS = frozenset(
    {
        "factorization_needs_resynthesis",
        "stance_review_needed",
        "split_possible",
        "insufficient_hints",
        "needs_human",
    }
)
CONFIDENCE_VALUES = frozenset({"high", "medium", "low"})
SIGN_MEANINGFUL_VALUES = frozenset(p.value for p in SIGN_MEANINGFUL_PREDICATES)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "onto",
        "than",
        "then",
        "when",
        "where",
        "which",
        "while",
    }
)


@dataclass(frozen=True)
class PropositionSnapshot:
    ref: str
    title: str
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    polarity: str | None = None
    claim_layer: str | None = None
    identification_strength: str | None = None
    source_refs: frozenset[str] = frozenset()
    paper_refs: frozenset[str] = frozenset()
    annotation_refs: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SameClaimCandidate:
    candidate_id: str
    propositions: tuple[str, ...]
    priority: Priority
    splittable: bool
    flags: tuple[str, ...]
    signals: Mapping[str, Any]
    explanation: tuple[str, ...]
    pair_edges: frozenset[tuple[str, str]] = frozenset()


@dataclass(frozen=True)
class FactorizationCandidate:
    candidate_id: str
    proposition: str
    priority: Priority
    papers: tuple[str, ...]
    current: Mapping[str, Any]
    observed_statement_hints: tuple[Mapping[str, Any], ...]
    disagreement: tuple[str, ...]
    recommended_action: str


@dataclass(frozen=True)
class ReconciliationFault:
    reason: str
    detail: str
    members: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReconciliationReport:
    same_claim_candidates: tuple[SameClaimCandidate, ...] = ()
    factorization_disagreements: tuple[FactorizationCandidate, ...] = ()
    faults: tuple[ReconciliationFault, ...] = ()
    summary: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SameClaimBuildResult:
    candidates: tuple[SameClaimCandidate, ...]
    faults: tuple[ReconciliationFault, ...]


def _digest(parts: list[str]) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def candidate_id(lane: str, refs: Sequence[str]) -> str:
    sorted_refs = sorted(refs)
    digest = _digest([lane, *sorted_refs])
    try:
        token = LANE_ID_TOKENS[lane]
    except KeyError as exc:
        raise ValueError(f"unknown reconciliation lane: {lane!r}") from exc
    return f"reconcile:{token}/{digest}"


def judgment_id(lane: str, decision: str, refs: Sequence[str]) -> str:
    return f"reconcile:judgment/{_digest([lane, decision, *sorted(refs)])}"


def normalize_phrase(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def predicate_compatible(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return left in SIGN_MEANINGFUL_VALUES and right in SIGN_MEANINGFUL_VALUES


def polarity_compatible(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    if left == right:
        return True
    return "unsigned" in {left, right} and {left, right} <= {"positive", "negative", "unsigned"}


def title_tokens(title: str) -> set[str]:
    tokens = set(_TOKEN_RE.findall(title.casefold()))
    return {token for token in tokens if len(token) >= 4 and token not in _STOPWORDS}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _pair_key(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left <= right else (right, left)


def _blocking_pairs(propositions: list[PropositionSnapshot]) -> set[tuple[str, str]]:
    buckets: dict[tuple[str, str], list[str]] = {}
    for prop in propositions:
        subject = normalize_phrase(prop.subject)
        object_ = normalize_phrase(prop.object)
        predicate = prop.predicate or ""
        if subject and predicate and object_:
            buckets.setdefault(("spo", f"{subject}\0{predicate}\0{object_}"), []).append(prop.ref)
        if subject and object_:
            buckets.setdefault(("so", f"{subject}\0{object_}"), []).append(prop.ref)
        for paper in prop.paper_refs:
            buckets.setdefault(("paper", paper), []).append(prop.ref)
        for token in title_tokens(prop.title):
            buckets.setdefault(("title-token", token), []).append(prop.ref)

    pairs: set[tuple[str, str]] = set()
    for refs in buckets.values():
        if len(refs) < 2:
            continue
        ordered = sorted(set(refs))
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                pairs.add(_pair_key(left, right))
    return pairs


def _pair_signals(
    left: PropositionSnapshot, right: PropositionSnapshot
) -> tuple[bool, dict[str, Any], tuple[str, ...], tuple[str, ...], Priority]:
    left_subject = normalize_phrase(left.subject)
    right_subject = normalize_phrase(right.subject)
    left_object = normalize_phrase(left.object)
    right_object = normalize_phrase(right.object)
    same_subject = bool(left_subject) and left_subject == right_subject
    same_object = bool(left_object) and left_object == right_object
    pred_ok = predicate_compatible(left.predicate, right.predicate)
    pol_ok = polarity_compatible(left.polarity, right.polarity)
    tokens_left = title_tokens(left.title)
    tokens_right = title_tokens(right.title)
    title_jaccard = _jaccard(tokens_left, tokens_right)
    shared_papers = sorted(left.paper_refs & right.paper_refs)
    full_structured = same_subject and same_object and left.predicate == right.predicate and pol_ok
    endpoint_compatible = same_subject and same_object and pred_ok
    lexical = (
        title_jaccard >= 0.55
        or bool(tokens_left and tokens_left <= tokens_right)
        or bool(tokens_right and tokens_right <= tokens_left)
    )
    include = endpoint_compatible or (bool(shared_papers) and lexical)

    flags: list[str] = []
    explanation: list[str] = []
    if same_subject and same_object:
        explanation.append("same subject/object")
    if pred_ok:
        explanation.append("compatible predicate")
    if not pol_ok and same_subject and same_object and pred_ok:
        flags.append("conflict_or_negation")
        include = True
    if title_jaccard >= 0.55:
        explanation.append("high title token overlap")
    if not (
        left.subject
        and left.object
        and left.predicate
        and right.subject
        and right.object
        and right.predicate
    ):
        flags.append("needs_factorization_context")

    signals = {
        "title_token_jaccard": round(title_jaccard, 3),
        "same_subject": same_subject,
        "same_object": same_object,
        "predicate_compatible": pred_ok,
        "polarity_compatible": pol_ok,
        "shared_source_papers": shared_papers,
    }
    if full_structured:
        priority: Priority = "high"
    elif endpoint_compatible and lexical:
        priority = "medium"
    elif include:
        priority = "low"
    else:
        priority = "low"
    return include, signals, tuple(sorted(set(flags))), tuple(explanation), priority


def build_same_claim_candidates(propositions: list[PropositionSnapshot]) -> SameClaimBuildResult:
    by_ref = {prop.ref: prop for prop in propositions}
    edges: dict[
        tuple[str, str], tuple[dict[str, Any], tuple[str, ...], tuple[str, ...], Priority]
    ] = {}
    for left_ref, right_ref in sorted(_blocking_pairs(propositions)):
        include, signals, flags, explanation, priority = _pair_signals(
            by_ref[left_ref], by_ref[right_ref]
        )
        if include:
            edges[(left_ref, right_ref)] = (signals, flags, explanation, priority)

    parent = {ref: ref for ref in by_ref}

    def find(ref: str) -> str:
        while parent[ref] != ref:
            parent[ref] = parent[parent[ref]]
            ref = parent[ref]
        return ref

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for left, right in edges:
        union(left, right)

    groups: dict[str, list[str]] = {}
    for ref in by_ref:
        groups.setdefault(find(ref), []).append(ref)

    candidates: list[SameClaimCandidate] = []
    faults: list[ReconciliationFault] = []
    for refs in sorted(tuple(sorted(group)) for group in groups.values() if len(group) > 1):
        group_edges = frozenset(edge for edge in edges if edge[0] in refs and edge[1] in refs)
        if len(refs) > MAX_RECONCILIATION_COMPONENT_SIZE:
            faults.append(ReconciliationFault("component-too-large", f"{len(refs)} propositions", refs))
            continue

        priorities = [edges[edge][3] for edge in group_edges]
        if "high" in priorities:
            priority: Priority = "high"
        elif "medium" in priorities:
            priority = "medium"
        else:
            priority = "low"
        flags = tuple(sorted({flag for edge in group_edges for flag in edges[edge][1]}))
        explanation = tuple(sorted({item for edge in group_edges for item in edges[edge][2]}))
        edge_signals = [edges[edge][0] for edge in group_edges]
        signals = {
            "pair_count": len(group_edges),
            "max_title_token_jaccard": max(
                signal["title_token_jaccard"] for signal in edge_signals
            ),
            "same_subject": any(signal["same_subject"] for signal in edge_signals),
            "same_object": any(signal["same_object"] for signal in edge_signals),
            "predicate_compatible": any(
                signal["predicate_compatible"] for signal in edge_signals
            ),
            "polarity_compatible": any(signal["polarity_compatible"] for signal in edge_signals),
            "shared_source_papers": tuple(
                sorted(
                    {
                        paper
                        for signal in edge_signals
                        for paper in signal["shared_source_papers"]
                    }
                )
            ),
        }
        candidates.append(
            SameClaimCandidate(
                candidate_id=candidate_id(LANE_SAME_CLAIM, list(refs)),
                propositions=refs,
                priority=priority,
                splittable=len(refs) > 2,
                flags=flags,
                signals=signals,
                explanation=explanation,
                pair_edges=group_edges,
            )
        )
    return SameClaimBuildResult(tuple(candidates), tuple(faults))


def _hint(assertion: Any) -> dict[str, Any]:
    return {
        "paper": assertion.paper_ref,
        "annotation": assertion.annotation_ref,
        "stance": assertion.stance,
        "section": assertion.section,
        "subject": assertion.subject,
        "object": assertion.object,
        "subject_concept": assertion.subject_concept,
        "object_concept": assertion.object_concept,
        "exact": assertion.statement_exact,
    }


def _distinct_normalized(values: Sequence[str | None]) -> set[str]:
    return {normalized for value in values if (normalized := normalize_phrase(value))}


def build_factorization_disagreements(
    propositions: Mapping[str, PropositionSnapshot],
    assertions: Sequence[Any],
) -> tuple[FactorizationCandidate, ...]:
    by_prop: dict[str, list[Any]] = {}
    for assertion in assertions:
        if assertion.proposition_ref in propositions:
            by_prop.setdefault(assertion.proposition_ref, []).append(assertion)

    out: list[FactorizationCandidate] = []
    for prop_ref, prop_assertions in sorted(by_prop.items()):
        if len(prop_assertions) < 2:
            continue
        prop = propositions[prop_ref]
        stances = {assertion.stance for assertion in prop_assertions}
        subjects = _distinct_normalized([assertion.subject for assertion in prop_assertions])
        objects = _distinct_normalized([assertion.object for assertion in prop_assertions])
        useful_hints = [
            assertion for assertion in prop_assertions if assertion.subject or assertion.object
        ]
        disagreement: list[str] = []
        recommended = ""
        priority: Priority = "medium"
        if "asserted" in stances and "negated" in stances:
            disagreement.append("stance mix requires review")
            recommended = "stance_review_needed"
            priority = "high"
        if len(subjects) > 1:
            disagreement.append("subject differs")
            recommended = recommended or "factorization_needs_resynthesis"
        if len(objects) > 1:
            disagreement.append("object differs")
            recommended = recommended or "factorization_needs_resynthesis"
        if useful_hints and not (prop.subject and prop.predicate and prop.object):
            disagreement.append(
                "current proposition is unfactored despite useful statement hints"
            )
            recommended = recommended or "factorization_needs_resynthesis"
        if not disagreement and len(prop_assertions) > 1 and not useful_hints:
            disagreement.append("multiple assertions have insufficient factorization hints")
            recommended = "insufficient_hints"
            priority = "low"
        if not disagreement:
            continue
        out.append(
            FactorizationCandidate(
                candidate_id=candidate_id(LANE_FACTORIZATION, [prop_ref]),
                proposition=prop_ref,
                priority=priority,
                papers=tuple(sorted({assertion.paper_ref for assertion in prop_assertions})),
                current={
                    "subject": prop.subject,
                    "predicate": prop.predicate,
                    "object": prop.object,
                    "polarity": prop.polarity,
                    "claim_layer": prop.claim_layer,
                },
                observed_statement_hints=tuple(_hint(assertion) for assertion in prop_assertions),
                disagreement=tuple(disagreement),
                recommended_action=recommended,
            )
        )
    return tuple(out)


def candidate_to_json(candidate: SameClaimCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "propositions": list(candidate.propositions),
        "priority": candidate.priority,
        "splittable": candidate.splittable,
        "flags": list(candidate.flags),
        "signals": dict(candidate.signals),
        "explanation": list(candidate.explanation),
    }


def factorization_to_json(candidate: FactorizationCandidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "proposition": candidate.proposition,
        "priority": candidate.priority,
        "papers": list(candidate.papers),
        "current": dict(candidate.current),
        "observed_statement_hints": [
            dict(item) for item in candidate.observed_statement_hints
        ],
        "disagreement": list(candidate.disagreement),
        "recommended_action": candidate.recommended_action,
    }


def fault_to_json(fault: ReconciliationFault) -> dict[str, Any]:
    return {
        "reason": fault.reason,
        "detail": fault.detail,
        "members": list(fault.members),
    }


def report_to_json(report: ReconciliationReport) -> dict[str, Any]:
    summary = {
        "same_claim_candidates": len(report.same_claim_candidates),
        "factorization_disagreements": len(report.factorization_disagreements),
        "faults": len(report.faults),
    }
    summary.update(report.summary)
    return {
        "summary": summary,
        "same_claim_candidates": [
            candidate_to_json(item) for item in report.same_claim_candidates
        ],
        "factorization_disagreements": [
            factorization_to_json(item) for item in report.factorization_disagreements
        ],
        "faults": [fault_to_json(item) for item in report.faults],
    }


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    return str(raw)


def snapshot_from_entity(entity: Any) -> PropositionSnapshot:
    source_refs = frozenset(str(ref) for ref in (getattr(entity, "source_refs", None) or []))
    return PropositionSnapshot(
        ref=str(entity.canonical_id),
        title=str(getattr(entity, "title", "") or ""),
        subject=getattr(entity, "subject", None),
        predicate=_enum_value(getattr(entity, "predicate", None)),
        object=getattr(entity, "object", None),
        polarity=_enum_value(getattr(entity, "polarity", None)),
        claim_layer=_enum_value(getattr(entity, "claim_layer", None)),
        identification_strength=_enum_value(
            getattr(entity, "identification_strength", None)
        ),
        source_refs=source_refs,
        paper_refs=frozenset(ref for ref in source_refs if ref.startswith("paper:")),
        annotation_refs=frozenset(ref for ref in source_refs if ref.startswith("annotation:")),
    )


def _scope_filter(
    snapshots: Mapping[str, PropositionSnapshot],
    assertions: Sequence[Any],
    *,
    proposition_ref: str | None,
    source_sidecar: str | None,
) -> tuple[dict[str, PropositionSnapshot], list[Any]]:
    scoped_assertions = list(assertions)
    scoped_refs: set[str] | None = None
    if proposition_ref is not None:
        scoped_refs = {proposition_ref}
        scoped_assertions = [
            assertion
            for assertion in scoped_assertions
            if assertion.proposition_ref == proposition_ref
        ]
    if source_sidecar is not None:
        scoped_assertions = [
            assertion for assertion in scoped_assertions if assertion.sidecar == source_sidecar
        ]
        source_refs = {assertion.proposition_ref for assertion in scoped_assertions}
        scoped_refs = source_refs if scoped_refs is None else scoped_refs & source_refs
    if scoped_refs is None:
        return dict(snapshots), scoped_assertions
    return {
        ref: snapshots[ref]
        for ref in sorted(scoped_refs)
        if ref in snapshots
    }, scoped_assertions


def build_reconciliation_report(
    project_root: Any,
    *,
    proposition_ref: str | None = None,
    source_sidecar: str | None = None,
) -> ReconciliationReport:
    from pathlib import Path

    from science_tool.annotation.cross_paper_evidence import (
        load_proposition_source_refs,
        scan_literature_assertions,
    )
    from science_tool.graph.sources import load_project_sources

    root = Path(project_root).resolve()
    sources = load_project_sources(root)
    snapshots = {
        str(entity.canonical_id): snapshot_from_entity(entity)
        for entity in sources.entities
        if getattr(entity, "kind", None) == "proposition"
    }
    assertions, scan_faults = scan_literature_assertions(
        root, load_proposition_source_refs(root)
    )
    scoped_snapshots, scoped_assertions = _scope_filter(
        snapshots,
        assertions,
        proposition_ref=proposition_ref,
        source_sidecar=source_sidecar,
    )
    same = build_same_claim_candidates(list(scoped_snapshots.values()))
    factors = build_factorization_disagreements(scoped_snapshots, scoped_assertions)
    faults = [
        ReconciliationFault(
            fault.reason,
            f"{fault.sidecar}:{fault.annotation_id} {fault.detail}",
        )
        for fault in scan_faults
    ]
    faults.extend(same.faults)
    return ReconciliationReport(
        same_claim_candidates=same.candidates,
        factorization_disagreements=factors,
        faults=tuple(faults),
    )
