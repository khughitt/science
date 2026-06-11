from __future__ import annotations

from dataclasses import dataclass

RESOLVED_ENGAGED = {"addressed", "accepted-real", "wont-fix"}
PENDING = {"open", "investigating"}


@dataclass(frozen=True)
class FlagDisposition:
    disposition: str
    change: str = ""


def engagement_verdict(*, has_report: bool, flags: list[FlagDisposition]) -> str:
    """Total function over the flag set's disposition state.

    NO-QA (no report) / NO-FLAGS / RESPONDED (all resolved-engaged) /
    IGNORED (all open) / PARTIAL (anything else, incl. any `investigating`).
    """
    if not has_report:
        return "NO-QA"
    if not flags:
        return "NO-FLAGS"
    if all(f.disposition in RESOLVED_ENGAGED for f in flags):
        return "RESPONDED"
    if all(f.disposition == "open" for f in flags):
        return "IGNORED"
    return "PARTIAL"


def iteration_verdict(*, chain_depth: int, flags: list[FlagDisposition]) -> str:
    """QA-RESPONSIVE requires BOTH a supersedes re-run (chain_depth >= 2) AND a
    flag `addressed` with a non-empty `change`. A change without a re-run stays
    SINGLE-RUN here (and RESPONDED on the engagement axis)."""
    has_qa_change = any(f.disposition == "addressed" and f.change for f in flags)
    if chain_depth >= 2 and has_qa_change:
        return "QA-RESPONSIVE"
    if chain_depth >= 2:
        return "RE-RAN-UNRELATED"
    return "SINGLE-RUN"
