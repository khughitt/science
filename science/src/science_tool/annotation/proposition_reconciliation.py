from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from science_model.reasoning import SIGN_MEANINGFUL_PREDICATES


LANE_SAME_CLAIM = "same_claim"
LANE_FACTORIZATION = "factorization_disagreement"
MAX_RECONCILIATION_COMPONENT_SIZE = 25

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
    priority: Literal["high", "medium", "low"]
    splittable: bool
    flags: tuple[str, ...]
    signals: dict[str, Any]
    explanation: tuple[str, ...]
    pair_edges: frozenset[tuple[str, str]] = frozenset()


@dataclass(frozen=True)
class FactorizationCandidate:
    candidate_id: str
    proposition: str
    priority: Literal["high", "medium", "low"]
    papers: tuple[str, ...]
    current: dict[str, Any]
    observed_statement_hints: tuple[dict[str, Any], ...]
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
    summary: dict[str, Any] = field(default_factory=dict)


def _digest(parts: list[str]) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def candidate_id(lane: str, refs: list[str] | tuple[str, ...]) -> str:
    sorted_refs = sorted(refs)
    digest = _digest([lane, *sorted_refs])
    token = "same-claim" if lane == LANE_SAME_CLAIM else "factorization"
    return f"reconcile:{token}/{digest}"


def judgment_id(lane: str, decision: str, refs: list[str] | tuple[str, ...]) -> str:
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
