"""The staged `--fail-on` gate ladder (umbrella design §6).

`validate` is report-only by default (Tier 0). A project advances the gate
explicitly via `code_gate:` in science.yaml, or ad hoc via `--fail-on`. The
ladder is cumulative: a tier gates its own rules plus every lower tier's. The
gate operates purely on `Result.rule` at the exit-code layer, leaving the
`Result` dataclass and the JSON output contract untouched.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from science_tool.validate.result import Result

# Ordered, cumulative. Index = severity of the gate; each tier adds its rules
# on top of every lower tier.
GATE_TIERS: tuple[str, ...] = (
    "report",
    "ghost-files",
    "decision-bearing-orphans",
    "hygiene",
)

# Rules introduced *at* each tier (not cumulative; see cumulative_rules()).
_TIER_RULES: dict[str, frozenset[str]] = {
    "report": frozenset(),
    "ghost-files": frozenset({"code.ghost", "code.malformed-block"}),
    "decision-bearing-orphans": frozenset({"code.orphaned-executable"}),
    "hygiene": frozenset(
        {
            "code.metadata-gap",
            "code.unresolved-task",
            "code.uncommitted",
            "code.hardcoded-path",
            "code.produced-by-unresolved",
            # `belief.refutation-masked` and `belief.single-source-ceiling` were gated here.
            # Both compared an AUTHORED belief magnitude against the computed one, and belief is
            # no longer authored (D5 / design rev 8), so they have no input and were removed.
            #
            # `refutation-masked` — an author asserting support while an unresolved decisive
            # refutation stands — is a real invariant, and it now has its home on the axis that IS
            # authored. It inherits the gated ERROR its belief-axis predecessor held.
            #
            # `single-source-ceiling` does NOT come back. Applied to `refuted` it would flag the
            # strongest possible refutation — one decisive independent test — as unfounded. The
            # ceiling does not merely fail to transfer to the verdict axis; it INVERTS.
            "verdict.refutation-masked",
            #
            # The other two verdict rules are deliberately UNGATED:
            #   `verdict.missing-basis`         — WARN. The basis contract is normative, but at
            #       least 11 of the 15 migrating verdicts cannot satisfy it today, so an ERROR
            #       would be an uncertified instrument failing real builds. It has its OWN ratchet,
            #       independent of the `hypothesis` kind's certification.
            #   `verdict.disagrees-with-computed` — a disagreement is information, not a fault.
            #       Gating it would make the check a ceiling on the authored verdict, which is
            #       exactly what design rev 8 point 4 forbids.
            "evidence.proxy-ungated",
            # The `hypothesis` kind is certified (D5): all 18 roots pinned, rendering, validating.
            # Its three kind-level rules ratchet to ERROR and gate HERE, and only for this kind --
            # the names are kind-scoped so an uncertified kind's identical finding stays a WARN that
            # gates nothing (`gated_findings` keys on rule name alone). `_CERTIFIED_KINDS` in
            # `kind_severity.py` and this list advance together, one kind per slice.
            #   `verdict.missing-basis` is NOT here: it is a rule-level ratchet on a different axis
            #   (>=11 of 15 verdicts have no basis today), independent of the kind's certification.
            "hypothesis.status-vocabulary",
            "hypothesis.dangling-lineage",
            "hypothesis.unbacked-inverse",
        }
    ),
}


def cumulative_rules(tier: str) -> frozenset[str]:
    """All rules gated at `tier`, inclusive of every lower tier."""
    index = GATE_TIERS.index(tier)
    rules: set[str] = set()
    for name in GATE_TIERS[: index + 1]:
        rules |= _TIER_RULES[name]
    return frozenset(rules)


def gated_findings(results: Iterable[Result], tier: str) -> list[Result]:
    """The findings whose rule is gated at `tier`."""
    rules = cumulative_rules(tier)
    return [result for result in results if result.rule in rules]


def resolve_gate_tier(fail_on: str | None, manifest: Mapping[str, Any]) -> str:
    """Resolve the active gate tier: --fail-on flag > science.yaml code_gate > 'report'."""
    if fail_on is not None:
        tier = fail_on
    else:
        raw = manifest.get("code_gate")
        tier = str(raw) if raw is not None else "report"
    if tier not in GATE_TIERS:
        raise ValueError(
            f"unknown code gate tier {tier!r}; expected one of {', '.join(GATE_TIERS)}"
        )
    return tier
