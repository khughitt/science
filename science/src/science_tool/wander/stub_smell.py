from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from science_tool.wander.context import ContextBundle

STALE_THRESHOLD_DAYS = 60
SHORT_CONTENT_THRESHOLD = 500


@dataclass(frozen=True)
class StubSignals:
    older_than_60_days: bool
    no_incoming_bears_on: bool
    no_active_references: bool
    short_or_unchanged: bool

    @property
    def is_stub_candidate(self) -> bool:
        return (
            self.older_than_60_days
            and self.no_incoming_bears_on
            and self.no_active_references
            and self.short_or_unchanged
        )


def compute_stub_signals(bundle: ContextBundle, *, today: date) -> StubSignals:
    older = (
        bundle.created_date is not None
        and (today - bundle.created_date).days > STALE_THRESHOLD_DAYS
    )
    short_or_unchanged = False
    if bundle.content_length is not None and bundle.content_length < SHORT_CONTENT_THRESHOLD:
        short_or_unchanged = True
    elif bundle.created_date is not None and bundle.mtime is not None and bundle.mtime <= bundle.created_date:
        short_or_unchanged = True

    return StubSignals(
        older_than_60_days=older,
        no_incoming_bears_on=not bundle.neighbors.bears_on_incoming,
        no_active_references=not bundle.active_references,
        short_or_unchanged=short_or_unchanged,
    )
