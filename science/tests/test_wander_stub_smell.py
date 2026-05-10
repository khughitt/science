from __future__ import annotations

from datetime import date

from science_tool.wander.context import ContextBundle
from science_tool.wander.neighbors import NeighborSet
from science_tool.wander.stub_smell import compute_stub_signals


def _bundle(**overrides) -> ContextBundle:
    base = dict(
        entity_id="hypothesis:h1",
        uri="https://example.org/hypothesis/h1",
        kind="hypothesis",
        label="x",
        freshness_state="fresh",
        weight=0.5,
        components={},
        source_path=None,
        mtime=None,
        content_length=None,
        created_date=None,
        neighbors=NeighborSet(),
        active_references=[],
    )
    base.update(overrides)
    return ContextBundle(**base)


def test_stub_candidate_when_all_four_signals_hold() -> None:
    bundle = _bundle(
        created_date=date(2026, 1, 1),
        content_length=120,
        mtime=date(2026, 1, 1),
    )

    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))

    assert signals.older_than_60_days is True
    assert signals.no_incoming_bears_on is True
    assert signals.no_active_references is True
    assert signals.short_or_unchanged is True
    assert signals.is_stub_candidate is True


def test_not_a_candidate_when_recently_created() -> None:
    bundle = _bundle(created_date=date(2026, 5, 1), content_length=10)
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.older_than_60_days is False
    assert signals.is_stub_candidate is False


def test_not_a_candidate_when_has_active_reference() -> None:
    from science_tool.wander.references import Reference

    bundle = _bundle(
        created_date=date(2026, 1, 1),
        active_references=[Reference(entity_id="task:t1", kind="task")],
        content_length=10,
    )
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.no_active_references is False
    assert signals.is_stub_candidate is False


def test_not_a_candidate_when_has_incoming_bears_on() -> None:
    bundle = _bundle(
        created_date=date(2026, 1, 1),
        neighbors=NeighborSet(bears_on_incoming=["article:a"]),
        content_length=10,
    )
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.no_incoming_bears_on is False
    assert signals.is_stub_candidate is False


def test_long_and_modified_content_is_not_short_or_unchanged() -> None:
    bundle = _bundle(
        created_date=date(2026, 1, 1),
        content_length=2000,
        mtime=date(2026, 4, 1),
    )
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.short_or_unchanged is False
    assert signals.is_stub_candidate is False


def test_missing_inputs_default_to_not_a_candidate() -> None:
    bundle = _bundle()
    signals = compute_stub_signals(bundle, today=date(2026, 5, 9))
    assert signals.is_stub_candidate is False
