# science/src/science_tool/annotation/selector.py
"""TextQuoteSelector resolution algorithm.

See docs/plans/historical/2026-05-10-annotation-system-spec.md §Span addressing.
The algorithm is uniqueness-preserving at every step: ambiguous matches
fall through rather than guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

from science_tool.annotation.model import TextQuoteSelector


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"           # anchored prefix+exact+suffix matched uniquely
    DEGRADED = "degraded"           # bare exact (or one-sided anchor) matched uniquely
    FUZZY = "fuzzy"                 # Levenshtein match with clear-margin
    SUPERSEDED = "superseded"       # no qualifying match


@dataclass(frozen=True)
class ResolutionResult:
    status: ResolutionStatus
    start: Optional[int] = None
    end: Optional[int] = None


# Fuzzy match acceptance threshold: best score must be ≤ this fraction of len(exact).
_FUZZY_MAX_RATIO = 0.05
# Clear-margin requirement: second-best score must be ≥ this multiple of best.
_FUZZY_MARGIN = 2.0
# Cost ceiling for the fuzzy fallback. The scan is O(windows · n · max_distance)
# per the capped Levenshtein, so a stale selector against a large source (e.g. a
# stale lifted-marker sidecar over a big .source.md) would scan the whole
# document and hang. Fuzzy is best-effort recovery: above this estimated
# comparison budget, bail to "no match" (→ SUPERSEDED) instead. The caller then
# treats the marker as not-lifted, which surfaces the stale sidecar rather than
# silently hiding it.
_FUZZY_MAX_COMPARISONS = 50_000_000


def resolve_selector(source_text: str, selector: TextQuoteSelector) -> ResolutionResult:
    """Resolve a TextQuoteSelector against the source text per the spec algorithm.

    Algorithm (per spec §Span addressing): each step requires a *unique* match.
    Fuzzy matching is only attempted when ``exact`` has zero occurrences in
    the source — multiple-match-without-disambiguation returns SUPERSEDED
    directly to avoid silent misattribution to a tied span.
    """
    exact = selector.exact
    prefix = selector.prefix
    suffix = selector.suffix

    # Step 1: anchored exact (prefix + exact + suffix), unique.
    if prefix or suffix:
        anchored = prefix + exact + suffix
        positions = _all_occurrences(source_text, anchored)
        if len(positions) == 1:
            start = positions[0] + len(prefix)
            return ResolutionResult(
                status=ResolutionStatus.RESOLVED, start=start, end=start + len(exact)
            )

    # Step 2: bare exact, unique → DEGRADED.
    bare_positions = _all_occurrences(source_text, exact)
    if len(bare_positions) == 1:
        start = bare_positions[0]
        return ResolutionResult(
            status=ResolutionStatus.DEGRADED, start=start, end=start + len(exact)
        )

    # Step 3: bare exact appears multiple times. Try one-sided anchors to
    # disambiguate. If still ambiguous, return SUPERSEDED (do NOT fall
    # through to fuzzy — fuzzy on multiple distance-0 candidates would
    # silently attribute to the first occurrence).
    if len(bare_positions) > 1:
        if prefix:
            left = _all_occurrences(source_text, prefix + exact)
            if len(left) == 1:
                start = left[0] + len(prefix)
                return ResolutionResult(
                    status=ResolutionStatus.DEGRADED,
                    start=start,
                    end=start + len(exact),
                )
        if suffix:
            right = _all_occurrences(source_text, exact + suffix)
            if len(right) == 1:
                start = right[0]
                return ResolutionResult(
                    status=ResolutionStatus.DEGRADED,
                    start=start,
                    end=start + len(exact),
                )
        return ResolutionResult(status=ResolutionStatus.SUPERSEDED)

    # Step 4: zero exact matches. Try fuzzy with margin requirement.
    assert len(bare_positions) == 0
    fuzzy = _fuzzy_unique_match(source_text, exact)
    if fuzzy is not None:
        return ResolutionResult(
            status=ResolutionStatus.FUZZY,
            start=fuzzy,
            end=fuzzy + len(exact),
        )

    # Step 5: superseded.
    return ResolutionResult(status=ResolutionStatus.SUPERSEDED)


def _all_occurrences(haystack: str, needle: str) -> list[int]:
    if not needle:
        return []
    out: list[int] = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            return out
        out.append(idx)
        start = idx + 1


def _fuzzy_unique_match(source_text: str, exact: str) -> Optional[int]:
    n = len(exact)
    if n == 0 or len(source_text) < n:
        return None
    max_distance = max(1, int(n * _FUZZY_MAX_RATIO))
    window_count = len(source_text) - n + 1
    if window_count * n * (max_distance + 1) > _FUZZY_MAX_COMPARISONS:
        return None  # pathological cost (e.g. stale selector vs large source)
    best_score = max_distance + 1
    best_offset = -1
    second_best = max_distance + 1
    for offset in range(0, len(source_text) - n + 1):
        window = source_text[offset : offset + n]
        d = _levenshtein_capped(window, exact, max_distance)
        if d < best_score:
            second_best = best_score
            best_score = d
            best_offset = offset
        elif d < second_best:
            second_best = d
    if best_offset < 0 or best_score > max_distance:
        return None
    # Clear-margin requirement.
    if second_best <= max_distance and second_best < best_score * _FUZZY_MARGIN:
        return None
    return best_offset


def _levenshtein_capped(a: str, b: str, max_distance: int) -> int:
    """Levenshtein distance, returning max_distance+1 if the true distance exceeds it.

    Equal-length inputs only (we only ever compare same-length windows).
    """
    if a == b:
        return 0
    n = len(a)
    if n != len(b):
        return max_distance + 1
    prev = list(range(n + 1))
    for i in range(1, n + 1):
        curr = [i] + [0] * n
        row_min = curr[0]
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > max_distance:
            return max_distance + 1
        prev = curr
    return prev[n]
