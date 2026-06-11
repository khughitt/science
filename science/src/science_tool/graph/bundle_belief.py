"""Bundle belief roll-up (design doc 2026-06-11-bundle-belief-rollup-design.md).

A hypothesis/mechanism bundle's belief is derived from its member propositions
under an explicit composition rule. v1 implements weakest-link only.
"""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import RDF, URIRef

from science_model.reasoning import CompositionRule
from .belief import BeliefMagnitude, BeliefResult, _MAG_ORDER
from .belief_scalar import BeliefScalar
from .io import CITO_NS, SCI_NS

_BUNDLE_TYPES: dict[str, URIRef] = {
    "hypothesis": SCI_NS.Hypothesis,
    "mechanism": SCI_NS.Mechanism,
}
_KIND_DEFAULT_RULE: dict[str, CompositionRule] = {
    "hypothesis": CompositionRule.CONJUNCTIVE,
    "mechanism": CompositionRule.ALL_STEPS,
}


def bundle_kind(knowledge, uri: URIRef) -> str | None:
    """Return 'hypothesis'/'mechanism' if `uri` is a bundle type, else None."""
    for kind, type_uri in _BUNDLE_TYPES.items():
        if (uri, RDF.type, type_uri) in knowledge:
            return kind
    return None


def bundle_members(knowledge, uri: URIRef) -> list[URIRef]:
    """Direct member propositions: forward sci:hasProposition ∪ reverse cito:discusses.

    Restricted to Proposition-typed targets; non-transitive; deterministic order.
    """
    members: list[URIRef] = []
    seen: set[URIRef] = set()

    def _add(node) -> None:
        if (
            isinstance(node, URIRef)
            and node not in seen
            and (node, RDF.type, SCI_NS.Proposition) in knowledge
        ):
            seen.add(node)
            members.append(node)

    for _, _, obj in knowledge.triples((uri, SCI_NS.hasProposition, None)):
        _add(obj)
    for subj, _, _ in knowledge.triples((None, CITO_NS.discusses, uri)):
        _add(subj)

    members.sort(key=str)
    return members


def resolve_composition_rule(provenance, uri: URIRef, kind: str) -> CompositionRule:
    """Authored sci:compositionRule if present, else the per-kind default."""
    value = provenance.value(uri, SCI_NS.compositionRule)
    if value is not None:
        return CompositionRule(str(value))
    return _KIND_DEFAULT_RULE[kind]


@dataclass(frozen=True)
class MemberBelief:
    member_uri: str
    belief: BeliefResult
    scalar: BeliefScalar | None
    rank_key: tuple
    reason: str | None = None


@dataclass(frozen=True)
class BundleBeliefResult:
    composition_rule: str
    magnitude: BeliefMagnitude          # = member_results[0].belief.magnitude (the min-rank_key member)
    capped_by_refutation: bool
    contested: bool
    scalar: BeliefScalar | None         # the min-rank_key member's band (the scalar driver = member_results[0])
    member_results: list[MemberBelief]  # sorted ascending by rank_key; [0] drives magnitude + scalar
    bottleneck_members: list[str]       # ORDINAL-only: members sharing the minimum magnitude (superset of the scalar driver)
    contested_members: list[str]
    unresolved_members: list[str]


def member_rank_key(belief: BeliefResult, scalar: BeliefScalar | None, member_uri: str) -> tuple:
    """Deterministic ascending order: ordinal magnitude, then scalar net-band lower
    (0.0 when the scalar layer is off), then member_uri as a total-order tiebreak."""
    lower = scalar.net_band[0] if scalar is not None else 0.0
    return (_MAG_ORDER.index(belief.magnitude), lower, member_uri)


def roll_up_weakest_link(members: list[MemberBelief], *, rule: CompositionRule) -> BundleBeliefResult:
    """v1 conjunction: the bundle is as believed as its weakest member.

    Refutation propagates as a SEPARATE boolean axis (OR across members), never
    folded into the magnitude ordinal.

    `bottleneck_members` is the ORDINAL-tied set — every member sharing the minimum
    magnitude (the explanatory "weakest-magnitude members"). The reported `magnitude`
    and `scalar` come from `member_results[0]` (minimum full `rank_key`), which is
    always within that set; when several members tie on ordinal but differ in
    net-band, `[0]` is the deterministic scalar driver and the others are still
    listed as bottlenecks for explanation. Every member's `scalar`/`rank_key` is
    retained in `member_results`, so the scalar driver is always identifiable.
    """
    ordered = sorted(members, key=lambda m: m.rank_key)
    bottleneck = ordered[0]
    bundle_magnitude = bottleneck.belief.magnitude
    return BundleBeliefResult(
        composition_rule=rule.value,
        magnitude=bundle_magnitude,
        capped_by_refutation=any(m.belief.capped_by_refutation for m in ordered),
        contested=any(m.belief.contested for m in ordered),
        scalar=bottleneck.scalar,
        member_results=ordered,
        bottleneck_members=[m.member_uri for m in ordered if m.belief.magnitude == bundle_magnitude],
        contested_members=[m.member_uri for m in ordered if m.belief.contested],
        unresolved_members=[m.member_uri for m in ordered if m.belief.magnitude == BeliefMagnitude.SPECULATIVE],
    )
