"""mint_id accepts existing_by_id map; merge_planned scales O(planned + existing)."""

from __future__ import annotations

import inspect
import time
from datetime import datetime, timezone

from science_tool.annotation.audit import merge_planned, mint_id
from science_tool.annotation.model import (
    Motivation,
    Sidecar,
    SpecificResource,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation


def _planned(i: int) -> PlannedAnnotation:
    return PlannedAnnotation(
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(
                exact=f"sentence number {i}.",
                prefix="", suffix="",
            ),
        ),
        annotation_type="bare-author-year",
        motivation=Motivation.CLASSIFYING,
        body=TextualBody(value="msg"),
        match_text=f"m{i}",
        source_name="lint:foo-v1",
    )


def test_mint_id_signature_takes_existing_by_id() -> None:
    """Signature change is the load-bearing API contract."""
    sig = inspect.signature(mint_id)
    assert "existing_by_id" in sig.parameters, (
        "mint_id must accept existing_by_id: dict[str, Annotation] "
        "(set-only is insufficient: base_id lookup also needs the map)"
    )


def test_merge_planned_handles_large_batch_in_reasonable_time() -> None:
    """Soft performance assertion: O(planned + existing), not O(planned × existing).

    With 500 existing rows and 500 fresh planned rows (no collisions),
    merge_planned should complete well under 1 second on commodity
    hardware. The threshold has a generous 10× margin to absorb CI
    variance; the goal is to catch regressions to O(N²) behavior, not
    to micro-benchmark.
    """
    now = datetime(2026, 5, 11, tzinfo=timezone.utc)
    initial_planned = [_planned(i) for i in range(500)]
    sidecar0, _ = merge_planned(
        Sidecar(), initial_planned, actor="t", now=now,
    )
    new_planned = [_planned(500 + i) for i in range(500)]
    start = time.perf_counter()
    sidecar1, written = merge_planned(
        sidecar0, new_planned, actor="t", now=now,
    )
    elapsed = time.perf_counter() - start
    assert len(written) == 500
    assert len(sidecar1.annotations) == 1000
    assert elapsed < 1.0, (
        f"merge_planned took {elapsed:.2f}s for 500+500 rows "
        "(suggests O(N²) regression in mint_id)"
    )
