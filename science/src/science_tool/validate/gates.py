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
            "belief.refutation-masked",
            "belief.single-source-ceiling",
            "evidence.proxy-ungated",
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
