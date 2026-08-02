"""Report agent confirmations that do not count as support (design §4.2.1, §5.4).

Non-gating and INFO. §4.2.1 excludes an agent confirmation two ways -- an `unwired`
correspondence, and a `verified` one whose evidence is empty or mixed with prose -- and
only the first was ever visible. A reader seeing three confirming reviews above
`confirmations: 2` deserves an account of the difference.

The predicate is `Review.counts_as_support()` itself, NOT a list of the correspondence
codes this module knows about: a roster would have a hole the day §5.3 gains a code.
"""

from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection, Review

from science_tool.findings.storage import case_path, load_cases
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.findings import validation_observation
from science_tool.validate.result import Severity

SECTION = FindingSection(
    id="review-confirmations",
    title="uncounted agent confirmations",
    section_order=161,
)


class UncountedConfirmationQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    review_id: str
    reason: str


RULE_UNCOUNTED_CONFIRMATION = FindingRule(
    id="review.uncounted-confirmation",
    severities=frozenset({"info"}),
    subject_types=frozenset({"path"}),
    qualifier_schema=UncountedConfirmationQualifiers,
    identity_qualifiers=("review_id",),
    title="Agent confirmation that does not count as support",
    section=SECTION.id,
    display_order=16101,
)


def _reason(review: Review) -> str:
    """Why this confirmation did not count. Derived, never authored."""
    correspondence = review.correspondence
    if correspondence is None:
        return "no correspondence was recorded"
    if correspondence.status != "verified":
        return f"correspondence is {correspondence.status} ({correspondence.code})"
    if not review.evidence:
        return "no location evidence"
    return "evidence mixes non-location entries"


@Check(
    section=SECTION,
    order=206,
    producer_id="validate.review-confirmations",
    rules=(RULE_UNCOUNTED_CONFIRMATION,),
)
def check_review_confirmations(ctx: ValidateContext) -> Iterator[CheckObservation]:
    for record in load_cases(ctx.project_root):
        for review in record.reviews:
            if review.reviewer_kind != "agent" or review.outcome != "confirms":
                continue
            if review.counts_as_support():
                continue
            reason = _reason(review)
            yield validation_observation(
                severity=Severity.INFO,
                path=case_path(ctx.project_root, record),
                line=None,
                message=(
                    f"agent confirmation {review.review_id} on {record.rule_id} does not "
                    f"count as support: {reason}"
                ),
                rule=RULE_UNCOUNTED_CONFIRMATION,
                task=None,
                qualifiers={"review_id": review.review_id, "reason": reason},
            )
