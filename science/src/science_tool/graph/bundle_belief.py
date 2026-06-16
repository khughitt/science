"""Bundle belief roll-up (design doc 2026-06-11-bundle-belief-rollup-design.md).

A hypothesis/mechanism bundle's belief is derived from its member propositions
under an explicit composition rule. v1 implements weakest-link only.
"""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import RDF, URIRef

from science_model.reasoning import CompositionRule, RESERVED_COMPOSITION_RULES
from .belief import aggregate_belief, BeliefMagnitude, BeliefResult, collect_evidence_units, _MAG_ORDER
from .belief_scalar import belief_scalar, BeliefScalar
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
    policy_id: str
    policy_version: str


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
    identities = {(m.belief.policy_id, m.belief.policy_version) for m in members}
    if len(identities) > 1:
        raise MixedBeliefPolicyError(
            f"cannot combine belief results computed under different policies: {sorted(identities)}"
        )
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
        policy_id=ordered[0].belief.policy_id,
        policy_version=ordered[0].belief.policy_version,
    )


class MixedBeliefPolicyError(ValueError):
    """Refuse to combine belief results computed under different BeliefPolicy identities."""


class UnresolvedBundleError(ValueError):
    """An authored bundle (or any mechanism) resolved to zero member propositions."""


def belief_for_entity(knowledge, provenance, uri, *, scalar_enabled: bool):
    """Dispatch: proposition → BeliefResult; hypothesis/mechanism → BundleBeliefResult.

    Returns BeliefResult | BundleBeliefResult.
    """
    rule_literal = provenance.value(uri, SCI_NS.compositionRule)
    authored_rule = CompositionRule(str(rule_literal)) if rule_literal is not None else None
    if authored_rule is not None and authored_rule in RESERVED_COMPOSITION_RULES:
        # Defensive: the model layer already rejects these at parse; never silently fall back.
        raise NotImplementedError(
            f"composition_rule {authored_rule.value!r} is reserved and not implemented in v1 "
            "(see docs/plans/2026-06-11-bundle-belief-rollup-design.md §4)."
        )

    kind = bundle_kind(knowledge, uri)
    if kind is None:
        if authored_rule is not None:
            # Defense in depth: the model layer rejects composition_rule on non-bundle kinds,
            # but a hand-authored graph could still carry one. Never silently ignore it.
            raise ValueError(
                f"{uri} carries composition_rule {authored_rule.value!r} but is not a bundle "
                "(hypothesis/mechanism); composition_rule is meaningless on non-bundle entities."
            )
        return aggregate_belief(collect_evidence_units(knowledge, provenance, [uri]))

    members = bundle_members(knowledge, uri)
    if not members:
        if authored_rule is not None or kind == "mechanism":
            raise UnresolvedBundleError(
                f"{uri} is a {kind} bundle with zero resolved member propositions "
                "(dangling has_proposition / discusses links?); refusing to collapse to "
                "direct-evidence belief."
            )
        return aggregate_belief(collect_evidence_units(knowledge, provenance, [uri]))

    rule = authored_rule or _KIND_DEFAULT_RULE[kind]
    member_beliefs: list[MemberBelief] = []
    for member in members:
        belief = aggregate_belief(collect_evidence_units(knowledge, provenance, [member]))
        scalar = belief_scalar(belief) if scalar_enabled else None
        reason = "speculative: no evidence" if belief.magnitude == BeliefMagnitude.SPECULATIVE else None
        member_beliefs.append(
            MemberBelief(
                member_uri=str(member),
                belief=belief,
                scalar=scalar,
                rank_key=member_rank_key(belief, scalar, str(member)),
                reason=reason,
            )
        )
    return roll_up_weakest_link(member_beliefs, rule=rule)
