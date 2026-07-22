"""Promote-time completeness measure for paper canonicals.

fb-2026-07-11-020. A promoted paper becomes the canonical entity every other
project reads. Two promoted papers (Boyle2023, Lutz2025) carried no Methods and
no Limitations section at all, so consumers could not assess evidential
strength. This module reports which evidential-strength sections a paper
canonical is missing, so the operator sees the gap at the moment the source
PDF is still at hand.

Like `promote_body_loss`, this only MEASURES. It decides nothing: the promote
command surfaces the gaps as a warning and the operator chooses. A paper that
legitimately has no formal Methods (a preprint, a commentary) is not blocked.

The report's other asks — warning when a project entity cites a claim absent
from the canonical body, and detecting a consumer overlay that contradicts its
canonical — are semantic judgements no check can make honestly, so they are not
attempted here.
"""

from __future__ import annotations

from collections.abc import Mapping

# The sections a consumer needs to weigh a paper's evidential strength. Both are
# declared canonical body sections for the paper profile
# (`read_canonical_body_sections`); this names the subset that is load-bearing
# for downstream reasoning rather than every declared heading.
REQUIRED_EVIDENTIAL_SECTIONS: tuple[str, ...] = ("Methods", "Limitations")


def paper_completeness_gaps(canonical_body: Mapping[str, str]) -> list[str]:
    """Evidential-strength sections absent or empty in a paper canonical body.

    `canonical_body` maps section name -> section text (as produced by
    `_classify_entity`). A section counts as present only when it carries
    non-whitespace text. Returns the missing sections in declared order.
    """
    gaps: list[str] = []
    for section in REQUIRED_EVIDENTIAL_SECTIONS:
        text = canonical_body.get(section)
        if not isinstance(text, str) or not text.strip():
            gaps.append(section)
    return gaps
