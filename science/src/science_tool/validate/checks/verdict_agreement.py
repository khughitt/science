"""Does an AUTHORED verdict agree with the COMPOSED evidence? — at graph time.

`verdict` is an ADJUDICATION, and an adjudication with nothing behind it is a fabrication. The
constraint is NOT conditional on the lifecycle: a `draft` hypothesis asserting `verdict: refuted`
with no basis is exactly as unfounded as a `complete` one.

THREE things this deliberately does NOT do:

1. It does not ORDINALIZE the verdict. `supported|partially-supported|weakened|refuted` is not a
   ladder -- a refuted core member is *expected* under `partially-supported`, `weakened` is
   temporal, and ONE decisive independent test can legitimately establish `refuted`. A
   single-source ceiling applied to `refuted` would flag the strongest possible refutation as
   unfounded. Compatibility is a MATRIX, not a comparison.
2. It does not FLATTEN member evidence. `belief_for_entity` composes (weakest-link over core
   members) so that strong evidence for one proposition cannot mask a speculative core member.
3. It does not WRITE. It reports a disagreement and never populates or overwrites the authored
   verdict (design rev 8 pt. 4). The moment it could, `verdict` would stop being an adjudication.

SCOPE -- stated, not assumed, because a basis this check cannot READ is a basis it must not CLAIM.
A qualifying basis is exactly one of two things, and their REACH DIFFERS:

  * an admissible, polarity-agreeing EVIDENCE-LINE unit -- on the hypothesis OR one of its CORE
    members. A hypothesis is a legal evidence target: the `supports`/`disputes` relation kinds
    declare target_kinds ["proposition", "hypothesis"] from an evidence-line source
    (profiles/core.py:648-660);
  * a FALSIFICATION record -- on a CORE PROPOSITION MEMBER, and ONLY there.

A falsification ON THE HYPOTHESIS cannot exist and is not looked for: `FalsificationEntity.falsifies`
is required, and `_add_falsification_relations` hard-raises unless it resolves to a proposition
("falsification targets must be propositions", materialize.py:1274).

INTERPRETATIONS are out of scope: `interpretation` is not a graph kind (no such entity in the
registry, no typed edge to a hypothesis), so design rev 8's "or interpretation basis" clause cannot
be enforced here. No message implies otherwise.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from rdflib import RDF, Graph, URIRef

from science_tool.graph.belief import (
    BeliefMagnitude,
    BeliefResult,
    aggregate_belief,
    collect_evidence_units,
    is_decisive_refutation,
)
from science_tool.graph.belief_scalar import belief_scalar_enabled
from science_tool.graph.bundle_belief import BundleBeliefResult, belief_for_entity
from science_tool.graph.io import SCI_NS, entity_uri_for_ref
from science_tool.graph.store import _graph_uri
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE_MISSING_BASIS = "verdict.missing-basis"
RULE_REFUTATION_MASKED = "verdict.refutation-masked"
RULE_DISAGREES = "verdict.disagrees-with-computed"

# Polarity agreement: which evidence STANCE can ground which verdict. An edge is not a basis --
# a `supports` line is not a basis for `refuted`.
_QUALIFYING_STANCES: dict[str, frozenset[str]] = {
    "supported": frozenset({"supports"}),
    # A refuted/disputed portion is exactly what `partially-supported` is FOR, so either stance
    # grounds it.
    "partially-supported": frozenset({"supports", "disputes"}),
    "weakened": frozenset({"disputes"}),
    "refuted": frozenset({"disputes"}),
}

# The verdicts a FALSIFICATION (a negative adjudication) can ground. `supported` is absent by
# construction: a record that a prediction failed cannot be the reason a hypothesis is supported.
_ADMITS_NEGATIVE_ADJUDICATION = frozenset({"partially-supported", "weakened", "refuted"})


@dataclass(frozen=True)
class _Composition:
    """One reading of the composed evidence, uniform over the bundle and direct branches.

    `belief_for_entity` returns a `BundleBeliefResult` when the hypothesis has core members and a
    plain `BeliefResult` otherwise (memberless, or all-rival). Both are read here so no caller has
    to branch on the type.
    """

    magnitude: BeliefMagnitude
    direct: BeliefResult          # evidence attached to the hypothesis IRI itself
    core: list[BeliefResult]      # per CORE member; empty when the hypothesis has none
    core_uris: list[URIRef]


@Check(section="verdict agreement", order=28)
def check_verdict_agreement(ctx: ValidateContext) -> Iterator[Result]:
    knowledge, provenance = _load_belief_graphs(ctx)
    if knowledge is None or provenance is None:
        return

    scalar_enabled = belief_scalar_enabled(ctx.project_root)
    path_by_uri = _paths_by_uri(ctx)

    for uri in sorted(_hypotheses(knowledge), key=str):
        raw = next(knowledge.objects(uri, SCI_NS.verdict), None)
        if raw is None:
            continue                  # absent == no adjudication recorded. Legal, and common.
        verdict = str(raw)

        composition = _compose(knowledge, provenance, uri, scalar_enabled=scalar_enabled)
        falsified = _has_falsified_core_member(knowledge, composition)
        path = path_by_uri.get(uri)

        # ☠️ NO `continue` BETWEEN THE RULES. They are INDEPENDENT: a `supported` hypothesis can
        # lack any supporting basis AND simultaneously mask a decisive refutation, and both are
        # true. Short-circuiting would skip the hard invariant for exactly the files with the
        # weakest evidentiary footing -- suppressing it where it matters most.
        if not _has_qualifying_basis(verdict, composition, falsified=falsified):
            yield Result(
                Severity.WARN,
                path,
                None,
                # The message names the basis the check ACTUALLY LOOKS FOR. Offering "or a
                # falsification on the hypothesis" would tell the author to write a record the
                # materializer refuses (materialize.py:1274). The two reaches differ; this says so.
                f"{uri}: verdict {verdict!r} has no qualifying basis (no admissible, "
                f"polarity-agreeing evidence line on the hypothesis or a core member, and no "
                f"falsification on a core proposition member). A verdict is an adjudication "
                f"OF something.",
                RULE_MISSING_BASIS,
                None,
            )

        # THE HARD INVARIANT. `supported` cannot stand on top of an unresolved decisive refutation
        # of the hypothesis or of its core conjunction. `partially-supported` is deliberately NOT
        # included: a refuted member is exactly what that verdict is for.
        if verdict == "supported" and _has_decisive_refutation(composition):
            yield Result(
                Severity.ERROR,
                path,
                None,
                f"{uri}: verdict 'supported' with an unresolved decisive refutation of the "
                f"hypothesis or a core member",
                RULE_REFUTATION_MASKED,
                None,
            )

        # Explanatory disagreement -- REPORT ONLY. Never a ceiling, never a rewrite.
        reason = _disagreement(verdict, composition, falsified=falsified)
        if reason is not None:
            yield Result(
                Severity.WARN,
                path,
                None,
                f"{uri}: authored verdict {verdict!r} disagrees with composed belief: {reason}",
                RULE_DISAGREES,
                None,
            )


# ---------------------------------------------------------------------------------------------
# reading the composition
# ---------------------------------------------------------------------------------------------


def _compose(
    knowledge: Graph, provenance: Graph, uri: URIRef, *, scalar_enabled: bool
) -> _Composition:
    """The authoritative composition, plus the two things it cannot see.

    ☠️ DIRECT whole-hypothesis evidence is collected SEPARATELY. When core members exist,
    `belief_for_entity` takes the bundle branch and NEVER calls `collect_evidence_units([uri])`
    (bundle_belief.py:215+), so a decisive refutation attached to the hypothesis ITSELF is invisible
    to it. Bundle dispatch would otherwise HIDE the very thing `verdict.refutation-masked` exists to
    catch.
    """
    composed = belief_for_entity(knowledge, provenance, uri, scalar_enabled=scalar_enabled)
    direct = aggregate_belief(collect_evidence_units(knowledge, provenance, [uri]))

    if isinstance(composed, BundleBeliefResult):
        return _Composition(
            magnitude=composed.magnitude,
            direct=direct,
            core=[member.belief for member in composed.member_results],
            core_uris=[URIRef(member.member_uri) for member in composed.member_results],
        )
    # Memberless, or every member is a rival/background: the composition IS the direct evidence.
    return _Composition(magnitude=composed.magnitude, direct=direct, core=[], core_uris=[])


def _admitted(composition: _Composition) -> Iterator[BeliefResult]:
    """Every belief in SCOPE: the hypothesis itself, and its CORE members.

    Rivals are excluded -- `belief_for_entity` already excludes them from the conjunction, so a
    check that counted them would contradict the composition it claims to read.
    """
    yield composition.direct
    yield from composition.core


def _portions(composition: _Composition) -> list[BeliefResult]:
    """The parts a `partially-supported` verdict is a verdict ABOUT.

    When the hypothesis has core members, the portions ARE those members. Otherwise the hypothesis
    itself is the only portion. (Not `_admitted`: for a bundle, the hypothesis's own direct belief
    is normally empty -- evidence lives on the members -- and reading that emptiness as "an
    unresolved portion" would make every bundle trivially partial.)
    """
    return composition.core if composition.core else [composition.direct]


def _has_decisive_refutation(composition: _Composition) -> bool:
    """An unresolved decisive refutation anywhere in scope.

    ☠️ NOT `capped_by_refutation`. That flag is True only when a decisive refutation pulled the
    magnitude DOWN (belief.py:365-368) -- so a claim with a decisive refutation and NO support
    composes to `speculative`, is never capped, and the flag reads False. That is precisely the
    `supported`-with-nothing-but-a-refutation case this rule exists to catch. Ask the real question:
    is there an ADMITTED decisive refuting unit? `dispute_units` is the reduced, admitted,
    non-diagnostic list -- the same list `aggregate_belief` itself tests.
    """
    return any(
        is_decisive_refutation(unit)
        for belief in _admitted(composition)
        for unit in belief.dispute_units
    )


def _has_stance(composition: _Composition, stances: frozenset[str]) -> bool:
    """An ADMITTED unit in scope whose stance is one of `stances`.

    Admissibility is not re-derived: `support_units`/`dispute_units` are what survived the belief
    policy (authored-confidence gate, circular exclusion, diagnostic split). A unit the policy
    excludes does not compose, and a unit that does not compose cannot adjudicate.
    """
    return any(
        unit.stance in stances
        for belief in _admitted(composition)
        for unit in (*belief.support_units, *belief.dispute_units)
    )


def _has_falsified_core_member(knowledge: Graph, composition: _Composition) -> bool:
    return any(
        next(knowledge.subjects(SCI_NS.falsifies, member), None) is not None
        for member in composition.core_uris
    )


# ---------------------------------------------------------------------------------------------
# the two rules
# ---------------------------------------------------------------------------------------------


def _has_qualifying_basis(
    verdict: str, composition: _Composition, *, falsified: bool
) -> bool:
    if _has_stance(composition, _QUALIFYING_STANCES[verdict]):
        return True
    return falsified and verdict in _ADMITS_NEGATIVE_ADJUDICATION


def _disagreement(verdict: str, composition: _Composition, *, falsified: bool) -> str | None:
    """The MATRIX. It does not compare rungs -- see this module's docstring."""
    if verdict == "supported":
        # ☠️ NOT `magnitude < supported`. One strong independent direct test composes to `fragile`
        # (well_supported needs >= 2 clean units; a lone unit is fragile by the corroboration rule),
        # so demanding the `supported` RUNG would warn on every verdict backed by a single decisive
        # experiment -- reimposing, on the verdict axis, the single-source ceiling this design
        # deleted. The honest complaint is that NOTHING composes, or that a refutation stands.
        if composition.magnitude == BeliefMagnitude.SPECULATIVE:
            return _speculative_reason(composition)
        if _has_decisive_refutation(composition):
            return "an unresolved decisive refutation stands"
        return None

    if verdict == "partially-supported":
        # A CONJUNCTION, not a disjunction. `partially-supported` says *some of it holds up and
        # some of it does not* -- so BOTH limbs must be present. Accepting an unsettled portion
        # ALONE let a hypothesis with nothing but a decisive dispute (or nothing but a
        # falsification, or no evidence at all) read as `partially-supported` in silence: with no
        # support anywhere, EVERY portion is unsettled by definition. Such a hypothesis is not
        # partially supported; it is UNSUPPORTED.
        if not _has_support(composition):
            return (
                "nothing is supported: no admissible supporting evidence on the hypothesis or "
                "on any core member"
            )
        if not _has_unsettled_portion(composition, falsified=falsified):
            return "nothing is partial: no unresolved or contested portion, and nothing refuted"
        return None

    if verdict == "weakened":
        # `weakened` asserts a CHANGE, and a change cannot be read from one snapshot: without a
        # prior `belief_snapshot` there is no trajectory. So the only thing this check may say is
        # that NOTHING disputes the hypothesis -- never that no weakening occurred.
        if _has_dispute(composition) or falsified:
            return None
        return "no disputing evidence and no negative adjudication exist"

    if verdict == "refuted":
        # NO single-source ceiling: one decisive independent test is a legitimate refutation.
        if _has_decisive_refutation(composition) or falsified:
            return None
        return "no decisive refutation and no linked falsification exist"

    return None


def _has_unsettled_portion(composition: _Composition, *, falsified: bool) -> bool:
    """Is any portion refuted, falsified, contested, or simply unsupported?

    HALF of `partially-supported` -- never the whole of it. On its own this is ALSO true of a
    hypothesis with no evidence whatsoever (every portion is speculative), which is exactly why the
    caller conjoins it with `_has_support`.
    """
    if _has_decisive_refutation(composition) or falsified:
        return True
    return any(
        belief.magnitude == BeliefMagnitude.SPECULATIVE or belief.contested
        for belief in _portions(composition)
    )


def _has_support(composition: _Composition) -> bool:
    return any(belief.support_units for belief in _admitted(composition))


def _has_dispute(composition: _Composition) -> bool:
    return any(belief.dispute_units for belief in _admitted(composition))


def _speculative_reason(composition: _Composition) -> str:
    """WHY the composition is speculative -- named from what was actually READ.

    ☠️ "no admissible evidence composes to any support at all" is a FALSE CLAIM whenever support
    exists but the CONJUNCTION is dragged down: `belief_for_entity` is weakest-link over core
    members, so an admissible supporting line directly on the hypothesis coexists with a speculative
    composition the moment one core member has no support of its own. Emitting the flat message
    there told the author to write evidence they had already written. Each branch below states only
    what it read.
    """
    if not _has_support(composition):
        return "no admissible evidence composes to any support at all"

    unsupported = [
        uri
        for uri, belief in zip(composition.core_uris, composition.core, strict=True)
        if not belief.support_units
    ]
    if unsupported:
        return (
            "admissible supporting evidence exists, but the weakest-link conjunction over core "
            "members stays speculative: no admissible support on "
            f"{', '.join(sorted(str(uri) for uri in unsupported))}"
        )
    return "the admissible supporting evidence is too weak to compose to any support"


# ---------------------------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------------------------


def _load_belief_graphs(ctx: ValidateContext) -> tuple[Graph | None, Graph | None]:
    path = ctx.project_root / "knowledge" / "graph.trig"
    if not path.exists():
        return None, None
    dataset = ctx.graph_dataset(path)
    return (
        dataset.graph(_graph_uri("graph/knowledge")),
        dataset.graph(_graph_uri("graph/provenance")),
    )


def _hypotheses(knowledge: Graph) -> Iterator[URIRef]:
    for subject, _, _ in knowledge.triples((None, RDF.type, SCI_NS.Hypothesis)):
        if isinstance(subject, URIRef):
            yield subject


def _paths_by_uri(ctx: ValidateContext) -> dict[URIRef, Path | None]:
    """Graph URI -> source file, built with the SAME function the materializer used.

    `entity_uri_for_ref(canonical_id)` is what minted the IRI in the graph, so this cannot drift
    from it the way a hand-rolled URI-to-id parse would.
    """
    sources = ctx.project_sources()
    path_by_id = {
        str(document.frontmatter.get("id")): document.path
        for document in sources.markdown_documents
        if document.frontmatter.get("id")
    }
    return {
        entity_uri_for_ref(entity.canonical_id): _as_path(path_by_id.get(entity.id))
        for entity in sources.entities
        if entity.kind == "hypothesis"
    }


def _as_path(raw: object) -> Path | None:
    return Path(str(raw)) if raw else None
