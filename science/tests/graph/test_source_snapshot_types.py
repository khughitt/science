"""Shape tests for the SourceSnapshot / SourceChange primitives (Slice B)."""

from __future__ import annotations

from datetime import date

from science_tool.graph.source_records import SourceChange, SourceSnapshot


def test_source_change_is_frozen_and_holds_hash_and_date():
    change = SourceChange(sha256="abc123", observed_on=date(2026, 6, 15))
    assert change.sha256 == "abc123"
    assert change.observed_on == date(2026, 6, 15)
    # frozen dataclass: assignment must raise
    try:
        change.sha256 = "x"  # type: ignore[misc]
    except Exception as exc:  # FrozenInstanceError
        assert "cannot assign" in str(exc).lower() or "frozen" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("SourceChange must be frozen")


def test_source_snapshot_defaults_latest_change_to_none():
    snap = SourceSnapshot(source_path="entities/hypotheses/h1.md", sha256="deadbeef")
    assert snap.source_path == "entities/hypotheses/h1.md"
    assert snap.sha256 == "deadbeef"
    assert snap.latest_change is None


def test_source_snapshot_carries_a_change():
    change = SourceChange(sha256="newhash", observed_on=date(2026, 6, 15))
    snap = SourceSnapshot(source_path="p.md", sha256="newhash", latest_change=change)
    assert snap.latest_change == change
